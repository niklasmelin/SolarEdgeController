import asyncio
import logging
import sys

from solar_controller.logger import setup_logger
from solar_controller.config import load_config
from solar_controller.factories.sensor_factory import create_sensor
from solar_controller.factories.inverter_factory import create_inverter
from solar_controller.controller.solar_regulator import SolarRegulator


async def main():
    """
    Main function to demonstrate the usage of EspReader.
    """
    # Set up logging (moved to logging.py)
    setup_logger()

    # Load all config values from config module
    config = load_config()

    # Create instances using factories
    reader = create_sensor(config)
    inverter = create_inverter(config)
    regulator = SolarRegulator()

    try:
        # Connect to the ESPHome device
        await reader.ensure_connected()
        if not reader._connected:
            logging.error("Failed to connect to ESPHome reader.")
            sys.exit(1)

        # Check inverter connection
        if not await inverter.check_connection():
            logging.error("Failed to connect to SolarEdge inverter.")
            sys.exit(1)

        for i in range(3):
            # Read data from inverter
            await inverter.read_all_registers()
            inverter_data = inverter.get_registers_as_json()
            solar_production = inverter_data["power_ac"]
            logging.debug(f"Current solar production: {solar_production} W")

            # Read data from ESPHome device
            sensor_esp = reader.get_data_as_json()
            current_export, current_export_time = sensor_esp[
                "momentary_active_import"
            ]
            current_import, current_export_time = sensor_esp[
                "momentary_active_export"
            ]
            # Apply scaling from kW to W
            current_export *= 1000
            current_import *= 1000
            logging.debug(
                f"Current export: {current_export} W, Current import: {current_import} W"
            )
            # Compute current active power consumption
            home_consumption = current_export - current_import
            logging.debug(f"Current home consumption: {home_consumption} W")

            # Compute new scale factor
            scale_factor = regulator.new_scale_factor(
                current_home_consumption=home_consumption,
                current_solar_production=inverter_data["power_ac"],
            )
            logging.debug(f"Computed scale factor: {scale_factor} %")

            # Apply new scale factor to inverter
            # await inverter.set_max_power_scale_factor(scale_factor)

            logging.info(
                f"Cycle {i+1}: Home Consumption = {home_consumption} W, "
                f"Solar Production = {solar_production} W, "
                f"New Scale Factor = {scale_factor} %"
            )

            # allow time for the device to push current states
            await asyncio.sleep(1)

        # Get ESPHome device
        grid_sensors = reader.get_sensor_data_as_json()
        print(grid_sensors)
        for info in grid_sensors.values():
            print(
                f"\t{info['object_id']:<36} "
                f"{info['name']:<36} "
                f"{str(info['value']):>8} "
                f"{info['unit']}"
            )
        # Get SolarEdge inverter data
        solaredge_sensors = inverter.get_registers_as_json()
        print(solaredge_sensors)
        for key, value in solaredge_sensors.items():
            val_display = "<no value>" if value is None else value
            print(f"\t{key:<36} {val_display:>12}")

    finally:
        await reader.disconnect()
        await inverter.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExport limiter stopped by user.")
