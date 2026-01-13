import asyncio
import logging
import math
import time
from typing import Any, Literal
from aioesphomeapi import (
    APIClient, APIConnectionError,
    SensorInfo, BinarySensorInfo, TextSensorInfo,
)


class ESPHomeReader:
    def __init__(
        self,
        host: str,
        port: int,
        encryption_key: str,
        reconnect_delay: float = 5.0,
    ):
        """
        Initialize an ESPHome reader instance.

        This class maintains a persistent, asynchronous connection to an ESPHome
        device, discovers all available entities, subscribes to state updates,
        and provides instant access to the latest sensor values along with
        per-sensor update timestamps.

        The connection is established lazily via `ensure_connected()` and is
        designed for long-running applications that repeatedly query sensor data.

        Parameters
        ----------
        host : str
            IP address or hostname of the ESPHome device.

        port : int
            TCP port of the ESPHome API (typically 6053).

        encryption_key : str
            ESPHome Noise protocol encryption key used to authenticate
            and encrypt the API connection.

        reconnect_delay : float, optional
            Number of seconds to wait before retrying a failed connection attempt.
            Defaults to 5.0 seconds.

        Notes
        -----
        - Calling `get_data_as_json()` before `ensure_connected()` will raise
        a RuntimeError.
        - All discovered entities are waited for on initial connection, up to
        a timeout, before data access is allowed.
        - Sensor values are updated asynchronously via ESPHome state callbacks.
        """

        self.host = host
        self.port = port
        self.encryption_key = encryption_key
        self.reconnect_delay = reconnect_delay

        self.client: APIClient | None = None

        self.meta: dict[int, tuple[str, str, str, Literal["sensor", "binary_sensor", "text_sensor"]]] = {}
        self.states: dict[int, dict[str, object]] = {}

        self._connected = False
        self._connecting_lock = asyncio.Lock()
        self._first_state_event = asyncio.Event()

        self.logger = logging.getLogger(self.__class__.__name__)

    # ---------- INTERNAL CALLBACK ----------
    def _on_state(self, msg: Any) -> None:
        """
        Callback for ESPHome state updates. This method is called by the ESPHome client when a new state update is received. It extracts the key, value, and last updated timestamp from the message and stores it in the internal cache.

        Parameters:
        -----------
        msg (Any): The ESPHome message containing the state update.

        Returns: None
        """
        key = getattr(msg, "key", None)
        if key not in self.meta:
            return

        kind = self.meta[key][3]
        value = None

        if kind == "sensor":
            value = msg.state
            if value is None or (isinstance(value, float) and math.isnan(value)):
                return
        elif kind == "binary_sensor":
            value = bool(msg.state)
        elif kind == "text_sensor":
            if msg.state is not None:
                value = msg.state

        # Store value with timestamp
        self.states[key] = {"value": value, "last_updated": time.time()}

        # 🔔 Signal first data
        if not self._first_state_event.is_set():
            self._first_state_event.set()

    # ---------- CONNECTION MANAGEMENT ----------
    async def connect(self) -> None:
        async with self._connecting_lock:
            if self._connected:
                return

            self.logger.info("Connecting to ESPHome device...")
            self.client = APIClient(
                self.host,
                self.port,
                password="",
                noise_psk=self.encryption_key,
            )

            try:
                await self.client.connect(login=True)
                await self._discover_entities()
                self.client.subscribe_states(self._on_state)

                self._connected = True
                self.logger.info(
                    "Connected. Discovered %d entities.", len(self.meta)
                )
            except APIConnectionError:
                self._connected = False
                self.logger.exception("ESPHome connection failed")
                raise

    async def disconnect(self):
        if self.client:
            self.logger.info("Disconnecting from ESPHome device")
            await self.client.disconnect()
            self.client = None
            self._connected = False

    async def _discover_entities(self):
        entities, _ = await self.client.list_entities_services()
        self.meta.clear()
        self.states.clear()

        for ent in entities:
            if isinstance(ent, SensorInfo):
                self.meta[ent.key] = (
                    ent.object_id,
                    ent.name,
                    ent.unit_of_measurement or "",
                    "sensor",
                )
            elif isinstance(ent, BinarySensorInfo):
                self.meta[ent.key] = (
                    ent.object_id,
                    ent.name,
                    "",
                    "binary_sensor",
                )
            elif isinstance(ent, TextSensorInfo):
                self.meta[ent.key] = (
                    ent.object_id,
                    ent.name,
                    "",
                    "text_sensor",
                )

        if not self.meta:
            raise RuntimeError("No ESPHome entities found")

    # ---------- PUBLIC API ----------
    async def ensure_connected(self, timeout: float = 3.0) -> None:
        """
        Connect and wait until all entities have reported at least once.
        Logs warnings for any entities that did not report in time.
        """
        while not self._connected:
            try:
                await self.connect()
            except APIConnectionError as e:
                self.logger.warning(f"Retrying ESPHome connection in {self.reconnect_delay}s, problem encountered {e}")
                await asyncio.sleep(self.reconnect_delay)
                continue

        # Wait until all entities have reported
        start_time = asyncio.get_event_loop().time()
        while True:
            missing = [k for k in self.meta if k not in self.states]
            if not missing:
                break  # all reported
            if asyncio.get_event_loop().time() - start_time > timeout:
                self.logger.warning("Some ESPHome sensors did not report in time: %s", missing)
                break
            await asyncio.sleep(0.05)  # check every 50ms

    def get_latest_states(self) -> dict:
        """
        Return the most recent raw sensor states received from the ESPHome device.

        This method provides an instantaneous, non-async snapshot of all sensor
        values that have been received so far, indexed by ESPHome entity key.
        Each entry includes both the latest value and the timestamp when that
        value was last updated.

        Returns
        -------
        dict[int, dict]
            A dictionary mapping ESPHome entity keys to state information.

            Each value has the following structure::

                {
                    "value": object,
                    "last_updated": float
                }

            Where:
            - ``value`` is the most recent sensor value. The type depends on the
            entity:
                * ``float`` or ``int`` for numeric sensors
                * ``bool`` for binary sensors
                * ``str`` for text sensors
            - ``last_updated`` is a Unix timestamp (as returned by ``time.time()``)
            indicating when the value was last received from the device.

        Notes
        -----
        - Sensors that have not yet reported a value will not appear in the
        returned dictionary.
        - The returned dictionary is a shallow copy of the internal state cache;
        modifying it will not affect the internal state.
        - This method does not perform any network I/O and returns immediately.

        Examples
        --------
        >>> states = reader.get_latest_states()
        >>> for key, state in states.items():
        ...     age = time.time() - state["last_updated"]
        ...     print(key, state["value"], f"{age:.1f}s ago")
        """
        return self.states.copy()

    def get_sensor_data_as_json(self) -> dict:
        """

        Return the latest ESPHome sensor data in a human-friendly JSON-like format.

        This method formats the most recent sensor values into a structured
        dictionary suitable for logging, display, or serialization. Each entry
        includes metadata discovered from the ESPHome device (object ID, name,
        unit), the latest formatted value, and the timestamp of the last update.

        The method is non-async and returns immediately using locally cached data.
        No network communication is performed.

        Returns
        -------
        dict[int, dict]
            A dictionary mapping ESPHome entity keys to formatted sensor data.

            Each value has the following structure::

                {
                    "object_id": str,
                    "name": str,
                    "unit": str,
                    "value": object,
                    "last_updated": float | None
                }

            Where:
            - ``object_id`` is the ESPHome object ID of the entity.
            - ``name`` is the human-readable name of the entity.
            - ``unit`` is the unit of measurement (empty string if not applicable).
            - ``value`` is the formatted sensor value:
                * ``float`` (rounded to one decimal place) for numeric sensors
                * ``"ON"`` or ``"OFF"`` for binary sensors
                * ``str`` for text sensors
                * ``"<no value>"`` if the entity has not yet reported a value
            - ``last_updated`` is a Unix timestamp (as returned by ``time.time()``)
            indicating when the value was last received, or ``None`` if no data
            has been received yet.

        Raises
        ------
        RuntimeError
            If the ESPHome device is not connected. Call ``ensure_connected()``
            before invoking this method.

        Notes
        -----
        - Sensors that have not yet reported a value will still appear in the
        returned dictionary, but with ``"<no value>"`` and ``last_updated=None``.
        - The returned dictionary is constructed on demand and does not modify
        internal state.
        - This method is safe to call repeatedly in tight loops.
        """
        if not self._connected:
            raise RuntimeError("ESPHome device not connected. Call ensure_connected() first.")

        data = {}
        for key, (obj_id, name, unit, kind) in self.meta.items():
            state = self.states.get(key)
            if state is None:
                value = "<no value>"
                last_updated = None
            else:
                value = state["value"]
                last_updated = state["last_updated"]
                if kind == "binary_sensor":
                    value = "ON" if value else "OFF"
                elif isinstance(value, (int, float)):
                    value = round(value, 1)

            data[key] = {
                "object_id": obj_id,
                "name": name,
                "unit": unit,
                "value": value,
                "last_updated": last_updated,
            }

        return data

    def get_data_as_json(self) -> dict[str, tuple[object, float | None]]:
        """
        Return a simplified mapping of sensor object_id → (value, last_updated).

        Example output:
            {
                "momentary_active_import": (1.6, 1768140230.9362214),
                "voltage_phase_1": (227.7, 1768140230.9363801),
                ...
            }

        Note
        ----
        - For sensors that have never reported a value, the value will be "<no value>"
        and the timestamp will be None.
        - This method does not perform any I/O and returns immediately.
        """
        if not self._connected:
            raise RuntimeError(
                "ESPHome device not connected. Call ensure_connected() first."
            )

        simplified: dict[str, tuple] = {}

        for key, (obj_id, name, unit, kind) in self.meta.items():
            state = self.states.get(key)

            if state is None:
                # Not reported yet
                simplified[obj_id] = ("<no value>", None)
            else:
                val = state["value"]
                ts = state["last_updated"]
                simplified[obj_id] = (val, ts)

        return simplified


# ------------------- EXAMPLE USAGE -------------------
async def main():
    reader = ESPHomeReader(
        host="192.168.1.2",
        port=6053,
        encryption_key="abcabcabcabcabcabcabcabcabcabcabcabcabcabca=",

    )

    await reader.ensure_connected()

    for i in range(3):
        data = reader.get_data_as_json()
        for info in data.values():
            ts = info["last_updated"]
            ts_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts)) if ts else "<no data>"
            print(
                f"{info['object_id']:<36} "
                f"{info['name']:<36} "
                f"{str(info['value']):>8} "
                f"{info['unit']:<6} "
                f"Last Updated: {ts_str}"
            )
        print(f"\n - Loop {i + 1} of 3")
        await asyncio.sleep(2)


if __name__ == "__main__":
    asyncio.run(main())
