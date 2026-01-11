import asyncio
import logging
from collections import deque
import sys

from .sensors.esphome_reader import ESPHomeReader
from .inverter.solaredge_inverter import SolarEdgeInverter
from .controller.solar_regulator import SolarRegulator

# --------------------- CONFIG ---------------------
ESP_READER_HOST = "192.168.30.182"
ESP_READERPORT = 6053
ESP_READERENCRYPTION_KEY = "004Nt8RGUB3CMOGb9vnY3sCblsx8vYbZSwrSwE2UbOE="  # base64-encoded 32-byte key
ESP_READERWINDOW_SECONDS = 0.5  # Reduced from 3 seconds

SOLAR_EDGE_INVERTER_DEVICE = "/dev/ttyUSB0"
SOLAR_EDGE_INVERTER_BAUD = 9600
SOLAR_EDGE_INVERTER_TIMEOUT = 2


# Configure the logger
logging.basicConfig(
    level=logging.INFO,  # Set the default logging level
    format="%(asctime)s - %(levelname)s - %(name)s - %(funcName)s - %(message)s",  # Log format
    datefmt="%Y-%m-%d %H:%M:%S"  # Date format
)

# Create a logger instance
logger = logging.getLogger("Solar Controller")

# Initialize EspReader with specific parameters
try:
    logger.info("Initializing ESPHome Reader...")
    reader = ESPHomeReader(
        host=ESP_READER_HOST,
        port=ESP_READERPORT,
        encryption_key=ESP_READERENCRYPTION_KEY,
    )
   
except Exception as e:
    logger.error(f"Failed to initialize ESPHome Reader: {e}")
    raise
    sys.exit(1)

# Instantiate the Solar Edge Inverter communication
try:
    # Initialize inverter
    logger.info("Initializing SolarEdge Inverter...")
    inverter = SolarEdgeInverter(
        device=SOLAR_EDGE_INVERTER_DEVICE,
        baud=SOLAR_EDGE_INVERTER_BAUD,
        timeout=SOLAR_EDGE_INVERTER_TIMEOUT,
    )
    
except Exception as e:
    logger.error(f"Failed to initialize inverter: {e}")
    raise
    sys.exit(1)

# Instantiate the Solar Regulator
try:
    logger.info("Initializing Solar Regulator...")
    regulator = SolarRegulator()
    
except Exception as e:
    logger.error(f"Failed to initialize Solar Regulator: {e}")
    raise
    sys.exit(1)
    

async def main():
    """
    Main function to demonstrate the usage of EspReader.
    """
    try:
        # Connect to the ESPHome device
        await reader.ensure_connected()
        if not reader._connected:
           logger.error("Failed to connect to ESPHome reader.")
           sys.exit(1)

        # Check inverter connection
        if not await inverter.check_connection():
            logger.error("Failed to connect to SolarEdge inverter.")
            sys.exit(1)
        
        for i in range(3):
            # Read data from inverter
            await inverter.read_all_registers()
            inverter_data = inverter.get_registers_as_json()
            solar_production = inverter_data['power_ac']
            logging.debug(f"Current solar production: {solar_production} W")

            # Read data from ESPHome device
            sensor_esp = reader.get_data_as_json()
            current_export, current_export_time = sensor_esp['momentary_active_import']
            current_import, current_export_time = sensor_esp['momentary_active_export']
            # Apply scaling from kW to W
            current_export *= 1000
            current_import *= 1000
            logging.debug(f"Current export: {current_export} W, Current import: {current_import} W")                        
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

            logger.info(
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
