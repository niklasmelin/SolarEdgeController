from solar_controller.sensors.esphome_reader import ESPHomeReader

def create_sensor(config):
    """Simple Factory: instantiate the configured sensor."""
    return ESPHomeReader(
        host=config.ESP_READER_HOST,
        port=config.ESP_READERPORT,
        encryption_key=config.ESP_READERENCRYPTION_KEY,
    )
