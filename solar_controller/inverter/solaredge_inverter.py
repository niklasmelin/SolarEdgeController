import asyncio
import logging
from typing import Optional, Dict, Any

import solaredge_modbus

from .solaredge_inverter_registers import REGISTERS, PollGroup


class SolarEdgeInverter(solaredge_modbus.Inverter):
    """
    SolarEdge Inverter interface with dynamic register handling.
    Blocks on Modbus I/O in a thread executor so async code can run without blocking the event loop.

    Provides:
    - Async connection check
    - Async register reads (all / poll / control / status)
    - Async writes for control registers
    - Register scaling and caching
    """

    def __init__(
        self, device: str = "/dev/ttyUSB0", baud: int = 9600, timeout: int = 2
    ):
        """
        Initialize the SolarEdgeInverter instance.

        :param device: path to serial device or TCP endpoint
        :param baud: serial baud rate
        :param timeout: Modbus timeout (s)
        """
        # Setup logger
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info("Initializing SolarEdgeInverter...")

        # Initialize base class (creates client etc.)
        super().__init__(device=device, baud=baud, timeout=timeout)

        # Initialize all register attributes to None
        for reg in REGISTERS.keys():
            setattr(self, reg, None)

    # -------------------------
    # Async Connection Helpers
    # -------------------------
    async def check_connection(self) -> bool:
        """
        Async check if inverter is reachable.
        Runs the blocking connect/disconnect in an executor.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, self._sync_check_connection
        )

    def _sync_check_connection(self) -> bool:
        """Blocking connection check implementation."""
        self.connect()
        try:
            return self.connected()
        finally:
            self.disconnect()

    # -------------------------
    # Async Register Reads
    # -------------------------
    async def read_all_registers(self) -> None:
        """
        Read all inverter registers (identity, poll, control, status).
        Can be awaited safely in async contexts.
        """
        self.logger.info("Reading all registers from inverter...")

        # Raw register map from blocking call
        loop = asyncio.get_running_loop()
        raw = await loop.run_in_executor(None, self._sync_read_all_registers)

        # Apply scaling to cached attributes
        self._apply_registers(raw, list(REGISTERS.keys()))

    def _sync_read_all_registers(self) -> Dict[str, Any]:
        """
        Blocking method: reads all registers via base .read_all() and returns raw data.
        """
        self.connect()
        try:
            return self.read_all()
        finally:
            self.disconnect()

    async def update_poll_registers(self) -> None:
        """Async update of poll group registers (AC/DC measurements)."""
        await self._async_update_group(PollGroup.POLL)

    async def update_control_registers(self) -> None:
        """Async update of control registers (settings/limits)."""
        await self._async_update_group(PollGroup.CONTROL)

    async def update_status_registers(self) -> None:
        """Async update of status registers."""
        await self._async_update_group(PollGroup.STATUS)

    async def _async_update_group(self, group: PollGroup) -> None:
        """
        Async wrapper that reads a register group in a thread executor.
        """
        loop = asyncio.get_running_loop()
        raw = await loop.run_in_executor(
            None, self._sync_update_register_group, group
        )
        # Apply scaling and caching
        regs = [r for r, v in REGISTERS.items() if v["group"] == group]
        self._apply_registers(raw, regs)

    def _sync_update_register_group(self, group: PollGroup) -> Dict[str, Any]:
        """Blocking update for a register group."""
        data: Dict[str, Any] = {}
        self.connect()
        try:
            if not self.connected():
                raise ConnectionError("Failed to connect to inverter")

            for name, props in REGISTERS.items():
                if props["group"] == group:
                    try:
                        data.update(self.read(name))
                    except Exception as exc:
                        self.logger.error(
                            "Error reading register %s: %s", name, exc
                        )
                        data[name] = None
            return data
        finally:
            self.disconnect()

    # -------------------------
    # Scaling & Assignment
    # -------------------------
    def _apply_registers(
        self, raw_registers: Dict[str, Any], keys: list[str]
    ) -> None:
        """
        Applies SunSpec scaling factors and caches the results on this object.

        :param raw_registers: raw register values (from Modbus)
        :param keys: list of register names to update
        """
        for key in keys:
            if key not in raw_registers:
                continue

            value = raw_registers[key]
            scale_key = REGISTERS[key]["scale"]

            if (
                value is not None
                and scale_key
                and scale_key in raw_registers
                and raw_registers[scale_key] is not None
            ):
                try:
                    value = float(value) * (10 ** int(raw_registers[scale_key]))
                except Exception as exc:
                    self.logger.warning(
                        "Scaling failed for %s: %s", key, exc
                    )

            setattr(self, key, value)

    # -------------------------
    # Output Helpers
    # -------------------------
    def get_registers_as_json(
        self, group: Optional[PollGroup] = None
    ) -> Dict[str, Any]:
        """
        Return a dictionary of cached register values.

        :param group: if specified, only include registers from that poll group
        """
        if group:
            return {r: getattr(self, r) for r, v in REGISTERS.items() if v["group"] == group}
        return {r: getattr(self, r) for r in REGISTERS.keys()}

    def print_registers(self, group: Optional[PollGroup] = None) -> None:
        """
        Nicely print cached registers.

        :param group: optionally print only a subset by poll group
        """
        data = self.get_registers_as_dict(group)
        print(f"\n{'Register':<30} | Value")
        print("-" * 45)
        for k, v in data.items():
            print(f"{k:<30} | {v}")
        print()

    # -------------------------
    # Async Power Control
    # -------------------------
    async def set_production_limit(self, limit: int) -> None:
        """
        Set the inverter production limit (0–100%).

        :param limit: percent of max power to allow
        """
        if not (0 <= limit <= 100):
            raise ValueError("Limit must be between 0 and 100.")

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None, self._sync_set_production_limit, limit
        )

    def _sync_set_production_limit(self, limit: int) -> None:
        """Blocking write for setting active power limit."""
        self.connect()
        try:
            if not self.connected():
                raise ConnectionError("Failed to connect to inverter")

            self.write("active_power_limit", limit)
        finally:
            self.disconnect()

    async def restore_power_control_defaults(self) -> None:
        """Restore inverter power control defaults asynchronously."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._sync_restore_defaults)

    def _sync_restore_defaults(self) -> None:
        """Blocking restore defaults implementation."""
        self.connect()
        try:
            if not self.connected():
                raise ConnectionError("Failed to connect to inverter")

            self.write("restore_power_control_default_settings", 1)
            self.write("active_power_limit", 100)
        finally:
            self.disconnect()
