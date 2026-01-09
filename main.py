import asyncio
import logging
from src.EspReader import EspReader
from src.SolarEdgeInverter import SolarEdgeInverter

# Configure the logger
logging.basicConfig(
    level=logging.INFO,  # Set the default logging level
    format="%(asctime)s - %(levelname)s - %(name)s - %(funcName)s - %(message)s",  # Log format
    datefmt="%Y-%m-%d %H:%M:%S"  # Date format
)

# Create a logger instance
logger = logging.getLogger("Power Controll")

# Instantiate the SolarEdgeInverter class
instance = SolarEdgeInverter(device="/dev/ttyUSB0", baud=9600, timeout=2)

# Initialize EspReader with specific parameters
reader = EspReader(host= "192.168.30.182",
                   port=6053,
                   encryption_key="004Nt8RGUB3CMOGb9vnY3sCblsx8vYbZSwrSwE2UbOE=",
                   )

async def main():
    """
    Main function to demonstrate the usage of EspReader.
    """
    try:
        # Connect to the ESPHome device
        await reader.ensure_connected()
        
        # Connect to the ESPHome device
        data = reader.get_data_as_json()
        for info in data.values():
            print(
                f"{info['object_id']:<36} "
                f"{info['name']:<36} "
                f"{str(info['value']):>8} "
                f"{info['unit']}"
            )
    finally:
        await reader.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
