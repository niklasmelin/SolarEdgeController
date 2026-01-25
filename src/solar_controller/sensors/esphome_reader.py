import asyncio
import logging
import math
import time
from typing import Any, Literal

from aioesphomeapi import (
    APIClient,
    APIConnectionError,
    SensorInfo,
    BinarySensorInfo,
    TextSensorInfo,
)


class ESPHomeReader:
    def __init__(
        self,
        host: str,
        port: int,
        encryption_key: str,
        reconnect_delay: float = 5.0,
        stale_timeout: float = 30.0,
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
        
        stale_timeout : float, optional
            Number of seconds without receiving any state updates before
            considering the connection stale and attempting to reconnect.

        Notes
        -----
        - Calling `get_data_as_json()` before `ensure_connected()` will raise
        a RuntimeError.
        - All discovered entities are waited for on initial connection, up to
        a timeout, before data access is allowed.
        - Sensor values are updated asynchronously via ESPHome state callbacks.
        `stale_timeout` seconds after connection.
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

        # NEW: watchdog state
        self._stale_timeout = float(stale_timeout)
        self._last_rx_monotonic: float | None = None
        self._watchdog_task: asyncio.Task | None = None
        self._reconnect_lock = asyncio.Lock()

    # ---------- INTERNAL CALLBACK ----------
    def _on_state(self, msg: Any) -> None:
        """Callback for ESPHome state updates."""
        # NEW: any update means the connection is alive
        self._last_rx_monotonic = time.monotonic()

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

        # Signal first data
        if not self._first_state_event.is_set():
            self._first_state_event.set()

    # ---------- NEW: WATCHDOG ----------
    def _ensure_watchdog(self) -> None:
        if self._watchdog_task is None or self._watchdog_task.done():
            self._watchdog_task = asyncio.create_task(self._watchdog_loop())

    async def _watchdog_loop(self) -> None:
        # simple polling interval; small enough to react quickly
        poll_s = max(1.0, min(2.0, self._stale_timeout / 10.0))

        while True:
            await asyncio.sleep(poll_s)

            if not self._connected:
                continue

            last = self._last_rx_monotonic
            if last is None:
                # connected but no first state yet; give it time
                continue

            if (time.monotonic() - last) <= self._stale_timeout:
                continue

            # stale stream => reconnect (serialize to avoid stampedes)
            async with self._reconnect_lock:
                # re-check inside lock
                last2 = self._last_rx_monotonic
                if (not self._connected) or (last2 is None):
                    continue
                if (time.monotonic() - last2) <= self._stale_timeout:
                    continue

                self.logger.warning(
                    "ESPHome stream stale (no updates for > %.1fs). Reconnecting...",
                    self._stale_timeout,
                )
                await self._reconnect_once()

    async def _reconnect_once(self) -> None:
        await self.disconnect()
        while not self._connected:
            try:
                await self.connect()
            except APIConnectionError as e:
                self.logger.warning(
                    "Reconnect failed, retrying in %ss, problem encountered %s",
                    self.reconnect_delay,
                    e,
                )
                await asyncio.sleep(self.reconnect_delay)

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

                # NEW: initialize RX time and start watchdog
                self._last_rx_monotonic = time.monotonic()
                self._ensure_watchdog()

                self.logger.info("Connected. Discovered %d entities.", len(self.meta))
            except APIConnectionError:
                self._connected = False
                self.logger.error("ESPHome connection failed")
                raise

    async def disconnect(self):
        if self.client:
            self.logger.info("Disconnecting from ESPHome device")
            await self.client.disconnect()
            self.client = None
        self._connected = False
        self._last_rx_monotonic = None
        self._first_state_event.clear()

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
        """Connect and wait until all entities have reported at least once."""
        while not self._connected:
            try:
                await self.connect()
            except APIConnectionError as e:
                self.logger.warning(
                    f"Retrying ESPHome connection in {self.reconnect_delay}s, problem encountered {e}"
                )
                await asyncio.sleep(self.reconnect_delay)
                continue

        # Wait until all entities have reported (kept as-is from your current code)
        start_time = asyncio.get_event_loop().time()
        while True:
            missing = [k for k in self.meta if k not in self.states]
            if not missing:
                break

            if asyncio.get_event_loop().time() - start_time > timeout:
                self.logger.warning("Some ESPHome sensors did not report in time: %s", missing)
                break

            await asyncio.sleep(0.05)

    def get_latest_states(self) -> dict:
        return self.states.copy()

    def get_sensor_data_as_json(self) -> dict:
        if not self._connected:
            raise RuntimeError("ESPHome device not connected. Call ensure_connected() first.")

        data = {}
        for key, (obj_id, name, unit, kind) in self.meta.items():
            state = self.states.get(key)
            if state is None:
                value = ""
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
        if not self._connected:
            raise RuntimeError("ESPHome device not connected. Call ensure_connected() first.")

        simplified: dict[str, tuple] = {}
        for key, (obj_id, _name, _unit, _kind) in self.meta.items():
            state = self.states.get(key)
            if state is None:
                simplified[obj_id] = ("", None)
            else:
                simplified[obj_id] = (state["value"], state["last_updated"])
        return simplified

    def get_control_data(self) -> dict[str, list[int | str | None]]:
        if not self._connected:
            raise RuntimeError("ESPHome device not connected. Call ensure_connected() first.")

        CONTROL_KEY_MAPPING = {
            "momentary_active_import": "grid_import_power",
            "momentary_active_export": "grid_export_power",
        }

        standardized: dict[str, list[int | str | None]] = {}
        for esphome_key, std_key in CONTROL_KEY_MAPPING.items():
            key = next((k for k, v in self.meta.items() if v[0] == esphome_key), None)
            if key is None:
                standardized[std_key] = ["", None]
                continue

            state = self.states.get(key)
            if state is None:
                standardized[std_key] = ["", None]
            else:
                val = int(state["value"] * 1000)  # kW to W
                standardized[std_key] = [val, state["last_updated"]]

        return standardized
