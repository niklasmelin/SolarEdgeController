import asyncio
import logging
import signal
import sys
import time

from solar_controller.config import load_config
from solar_controller.server import start_server, STATUS, HISTORY, CONTROL
from solar_controller.factories.sensor_factory import create_sensor
from solar_controller.factories.inverter_factory import create_inverter
from solar_controller.controller.solar_regulator import SolarRegulator


async def main(stop_event: asyncio.Event | None = None):
    """
    Main async loop for Solar Controller.
    Gracefully handles signals to allow clean shutdown.
    """
    # Use provided stop_event or create a new one
    stop_event = stop_event or asyncio.Event()

    # Only register OS signals if no stop_event was provided (i.e., production)
    if stop_event.is_set() is False:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop_event.set)

    # Load config (logger configured automatically)
    config = load_config()

    # Create instances using factories
    reader = create_sensor(config.esp_sensor)
    inverter = create_inverter(config.inverter)
    regulator = SolarRegulator()

    # Start HTTP heartbeat server
    asyncio.create_task(start_server(config, regulator, inverter=inverter))

    # Connect to devices
    await reader.ensure_connected()
    if not reader._connected:
        logging.error("Failed to connect to ESPHome reader.")
        sys.exit(1)

    if not await inverter.check_connection():
        logging.error("Failed to connect to SolarEdge inverter.")
        sys.exit(1)

    # Initial CONTROL values
    new_current_price = 0.0
    new_negative_price = False

    i = 0
    try:
        while not stop_event.is_set():
            # --- Read CONTROL values ---
            # {"limit_export": false, "auto_mode": true, "auto_mode_threshold": 0.0, "power_limit": 0.0}
            try:
                limit_export = bool(CONTROL.get("limit_export", False))
                auto_mode = bool(CONTROL.get("auto_mode", True))
                auto_mode_threshold = float(CONTROL.get("auto_mode_threshold", regulator.MAX_EXPORT_W))
                power_limit_W = float(CONTROL.get("power_limit_W", regulator.PEAK_PRODUCTION_W))
            except TypeError as e:
                logging.warning(f"Invalid CONTROL values: {CONTROL}, error: {e}. Using defaults.")
                limit_export = False
                auto_mode = True
                auto_mode_threshold = regulator.MAX_EXPORT_W
                power_limit_W = regulator.PEAK_PRODUCTION_W
            
            # --- Inverter ---
            await inverter.read_all_registers()
            inverter_data = inverter.get_registers_as_json()
            solar_production = inverter_data["power_ac"]
            logging.debug(f"Current solar production: {solar_production} W")

            # --- ESPHome sensor ---
            sensor_esp = reader.get_control_data()
            current_export, _ = sensor_esp["grid_export_power"]
            current_import, _ = sensor_esp["grid_import_power"]

            logging.debug(f"Current export: {current_export} W, Current import: {current_import} W")

            # --- Compute consumption ---
            if not isinstance(current_import, int) or not isinstance(current_export, int):
                logging.warning(f"Invalid sensor readings: Import {current_import} W, Export {current_export} W, skipping this cycle.")
                await asyncio.sleep(10)
                continue
            grid_consumption = current_import - current_export
            home_consumption = abs(solar_production - grid_consumption)
            logging.debug(f"Grid consumption: {grid_consumption} W, Home consumption: {home_consumption} W")

            # --- Compute new scale factor ---
            scale_factor = regulator.new_scale_factor(
                current_grid_consumption=grid_consumption,
                current_solar_production=solar_production,
                limit_export=limit_export,
                auto_mode=auto_mode,
                auto_mode_threshold=auto_mode_threshold,
                power_limit_W=power_limit_W
            )
            logging.debug(f"Computed scale factor: {scale_factor} %")

            logging.info(
                f"Cycle {i+1}: Grid={grid_consumption} W, Home={home_consumption} W, "
                f"Solar={solar_production} W, Scale Factor={scale_factor} %"
                f", Price={new_current_price} kr/kWh, Negative Price={new_negative_price}"
            )

            # --- Update STATUS, HISTORY, CONTROL ---
            STATUS.update({
                "grid_consumption": grid_consumption,
                "home_consumption": home_consumption,
                "solar_production": solar_production,
                "new_scale_factor": scale_factor,
                "last_update": time.time(),
                "power_limit_W": power_limit_W,
                "inverter_min_power_W": regulator.MIN_PRODUCTION_W,
                "inverter_max_power_W": regulator.PEAK_PRODUCTION_W,
                })
            
            for key in HISTORY:
                HISTORY[key].append(STATUS[key])

            i += 1
            await asyncio.sleep(10)  # loop interval

    except Exception as e:
        logging.exception("Exception in main loop: %s", e)

    finally:
        logging.info("Shutting down, disconnecting devices...")
        await reader.disconnect()
        # await inverter.disconnect()
        logging.info("Shutdown complete.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nSolar controller stopped by user.")
