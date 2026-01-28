import asyncio
import logging
import re
import time
from typing import Optional, Dict, Any

import solaredge_modbus

from .solaredge_inverter_registers import REGISTERS, PollGroup


class SolarEdgeInverter(solaredge_modbus.Inverter):
    """
    SolarEdge Inverter interface with dynamic register handling.

    Important for Home Assistant unique_id stability:
      Call `await inverter.update_identity_registers()` once during startup.
      This "locks" the serial number the first time it is successfully read.
    """

    _SERIAL_RE = re.compile(r"^[A-Za-z0-9-]+$")

    def __init__(self, device: str = "/dev/ttyUSB0", baud: int = 9600, timeout: int = 2) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info("Initializing SolarEdgeInverter...")
        super().__init__(device=device, baud=baud, timeout=timeout)

        # Initialize all register attributes to None
        for reg in REGISTERS.keys():
            setattr(self, reg, None)

        # Last successful update timestamp
        self.last_updated: float = 0.0

        # Serial number is read once and then treated as read-only.
        self._locked_serial: Optional[str] = None

    # -------------------------
    # Async Connection Helpers
    # -------------------------
    async def check_connection(self) -> bool:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._sync_check_connection)

    def _sync_check_connection(self) -> bool:
        self.connect()
        try:
            return self.connected()
        finally:
            self.disconnect()

    # -------------------------
    # Async Register Reads
    # -------------------------
    async def read_all_registers(self) -> None:
        self.logger.info("Reading all registers from inverter...")
        loop = asyncio.get_running_loop()
        raw = await loop.run_in_executor(None, self._sync_read_all_registers)
        self._apply_registers(raw, list(REGISTERS.keys()))
        self.last_updated = time.time()

    def _sync_read_all_registers(self) -> Dict[str, Any]:
        self.connect()
        try:
            return self.read_all()
        finally:
            self.disconnect()

    async def update_identity_registers(self) -> None:
        """
        Read SunSpec identity registers once and lock serial number.

        This prevents Home Assistant entity unique_ids from changing later
        due to transient None/unknown serial values.
        """
        await self._async_update_group(PollGroup.IDENTITY)

        serial_raw = getattr(self, "c_serialnumber", None)
        serial = str(serial_raw).strip() if serial_raw is not None else ""

        if not serial:
            raise RuntimeError("Failed to read inverter serial number (c_serialnumber is empty/None).")

        if not self._SERIAL_RE.fullmatch(serial):
            raise RuntimeError(f"Inverter serial number has unexpected format: {serial!r}")

        if self._locked_serial is None:
            self._locked_serial = serial
            self.logger.info("Locked inverter serial number: %s", serial)
        elif serial != self._locked_serial:
            raise RuntimeError(
                f"Inverter serial number changed from {self._locked_serial!r} to {serial!r}; refusing."
            )

    async def update_poll_registers(self) -> None:
        await self._async_update_group(PollGroup.POLL)

    async def update_control_registers(self) -> None:
        await self._async_update_group(PollGroup.CONTROL)

    async def update_status_registers(self) -> None:
        await self._async_update_group(PollGroup.STATUS)

    async def _async_update_group(self, group: PollGroup) -> None:
        loop = asyncio.get_running_loop()
        raw = await loop.run_in_executor(None, self._sync_update_register_group, group)
        regs = [r for r, v in REGISTERS.items() if v.group == group]
        self._apply_registers(raw, regs)
        self.last_updated = time.time()

    def _sync_update_register_group(self, group: PollGroup) -> Dict[str, Any]:
        data: Dict[str, Any] = {}
        self.connect()
        try:
            if not self.connected():
                raise ConnectionError("Failed to connect to inverter")
            for name, reg in REGISTERS.items():
                if reg.group == group:
                    try:
                        data.update(self.read(name))
                    except Exception as exc:
                        self.logger.error("Error reading register %s: %s", name, exc)
                        data[name] = None
            return data
        finally:
            self.disconnect()

    # -------------------------
    # Scaling & Assignment
    # -------------------------
    def _apply_registers(self, raw_registers: Dict[str, Any], keys: list[str]) -> None:
        for key in keys:
            if key not in raw_registers:
                continue

            value = raw_registers[key]
            scale_key = REGISTERS[key].scale
            if (
                value is not None
                and scale_key
                and scale_key in raw_registers
                and raw_registers[scale_key] is not None
            ):
                try:
                    value = float(value) * (10 ** int(raw_registers[scale_key]))
                except Exception as exc:
                    self.logger.warning("Scaling failed for %s: %s", key, exc)

            setattr(self, key, value)

    # -------------------------
    # Output Helpers
    # -------------------------
    @property
    def serial_number(self) -> Optional[str]:
        """Stable inverter serial number (only set after update_identity_registers)."""
        return self._locked_serial

    def get_registers_as_json(self, group: Optional[PollGroup] = None) -> Dict[str, Any]:
        if group:
            return {r: getattr(self, r) for r, v in REGISTERS.items() if v.group == group}
        return {r: getattr(self, r) for r in REGISTERS.keys()}

    def get_ha_sensors(self, group: Optional[PollGroup] = None) -> Dict[str, dict]:
        """
        Returns a dictionary of Home Assistant–ready sensor data with scaling applied.
        :param group: Optional PollGroup to filter (e.g., PollGroup.POLL)
        :return: dict keyed by register name containing HA sensor metadata and state
        """
        serial = self.serial_number
        if not serial:
            raise RuntimeError(
                "Inverter identity not initialized (serial_number is missing). "
                "Call update_identity_registers() once during startup."
            )

        sensors: Dict[str, dict] = {}
        for name, reg in REGISTERS.items():
            if group and reg.group != group:
                continue
            if not reg.ha:
                continue
            if name.endswith("_scale"):
                continue

            value = getattr(self, name, None)

            sensors[name] = {
                "state": value,
                "unit": reg.ha.unit,
                "device_class": reg.ha.device_class,
                "state_class": reg.ha.state_class,
                "entity_category": reg.ha.entity_category,
                "icon": reg.ha.icon,
                "friendly_name": reg.ha.friendly_name or name.replace("_", " ").title(),
                "description": reg.ha.description,
                "unique_id": f"{serial}_{name}",
                "available": value is not None,
            }

        return sensors

    def get_control_data(self) -> Dict[str, Any]:
        control_data: Dict[str, Any] = {}
        current_data = {r: getattr(self, r) for r, v in REGISTERS.items() if v.group == PollGroup.POLL}
        control_data["solar_production"] = current_data.get("power_ac")
        control_data["power_limit"] = getattr(self, "active_power_limit", None)
        control_data["last_updated"] = getattr(self, "last_updated", None)
        return control_data

    def print_registers(self, group: Optional[PollGroup] = None) -> None:
        data = self.get_registers_as_json(group)
        print(f"\n{'Register':<30} | Value")
        print("-" * 45)
        for k, v in data.items():
            print(f"{k:<30} | {v}")
        print()

    # -------------------------
    # Async Power Control
    # -------------------------
    async def set_production_limit(self, limit: int) -> None:
        if not (0 <= limit <= 100):
            raise ValueError("Limit must be between 0 and 100.")
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._sync_set_production_limit, limit)

    def _sync_set_production_limit(self, limit: int) -> None:
        self.connect()
        try:
            if not self.connected():
                raise ConnectionError("Failed to connect to inverter")
            self.write("active_power_limit", limit)
        finally:
            self.disconnect()

    async def restore_power_control_defaults(self) -> None:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._sync_restore_defaults)

    def _sync_restore_defaults(self) -> None:
        self.connect()
        try:
            if not self.connected():
                raise ConnectionError("Failed to connect to inverter")
            self.write("restore_power_control_default_settings", 1)
            self.write("active_power_limit", 100)
        finally:
            self.disconnect()
