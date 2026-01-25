import asyncio
import logging
import signal
import sys

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
    asyncio.create_task(start_server(config, inverter=inverter))

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
            if not isinstance(new_current_price, float) or not isinstance(new_negative_price, bool):
                logging.warning("Invalid price reading or negative_price, skipping this cycle.")
                await asyncio.sleep(10)
                continue
            
            scale_factor = regulator.new_scale_factor(
                current_grid_consumption=grid_consumption,
                current_solar_production=solar_production,
                updated_current_price=new_current_price,
                updated_negative_price=new_negative_price
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
            })
            for key in HISTORY:
                HISTORY[key].append(STATUS[key])

            new_current_price = CONTROL.get("current_price")
            new_negative_price = CONTROL.get("negative_price")

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
