from solar_controller.sensors.esphome_reader import ESPHomeReader
from solar_controller.config import ESPSensorConfig


def create_sensor(config: ESPSensorConfig) -> ESPHomeReader:
    """Instantiate the configured ESPHome sensor."""
    return ESPHomeReader(
        host=config.reader_host,
        port=config.reader_port,
        encryption_key=config.encryption_key,
    )
