from dataclasses import dataclass
import confuse
import logging

@dataclass
class ESPSensorConfig:
    reader_host: str
    reader_port: int
    encryption_key: str
    window_seconds: float

@dataclass
class InverterConfig:
    device: str
    baud: int
    timeout: int

@dataclass
class AppConfig:
    esp_sensor: ESPSensorConfig
    inverter: InverterConfig
    api_token: str
    debug_level: str

def load_config(config_file: str = "config.yaml") -> AppConfig:
    cfg = confuse.Configuration("solar_controller", __name__)
    cfg.set_file(config_file)

    # Load sections
    esp_sensor = ESPSensorConfig(
        reader_host=cfg["ESP_SENSOR"]["ESP_READER_HOST"].get(str),
        reader_port=cfg["ESP_SENSOR"]["ESP_READER_PORT"].get(int),
        encryption_key=cfg["ESP_SENSOR"]["ESP_READER_ENCRYPTION_KEY"].get(str),
        window_seconds=cfg["ESP_SENSOR"]["ESP_READER_WINDOW_SECONDS"].get(float),
    )

    inverter = InverterConfig(
        device=cfg["INVERTER"]["SOLAR_EDGE_INVERTER_DEVICE"].get(str),
        baud=cfg["INVERTER"]["SOLAR_EDGE_INVERTER_BAUD"].get(int),
        timeout=cfg["INVERTER"]["SOLAR_EDGE_INVERTER_TIMEOUT"].get(int),
    )

    api_token = cfg["API"]["TOKEN"].get(str)
    debug_level = cfg["DEBUG_LEVEL"].get(str)

    # --- Configure logging here ---
    log_level = getattr(logging, debug_level.upper(), logging.INFO)
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Only add a handler if none exist
    if not root_logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)

    # Optional: reduce noisy libraries
    logging.getLogger("aiohttp.access").setLevel(logging.WARNING)
    logging.getLogger("pymodbus").setLevel(logging.WARNING)
    logging.getLogger("aioesphomeapi.connection").setLevel(logging.WARNING)

    logging.info(f"Logger configured with level {debug_level.upper()}")

    return AppConfig(
        esp_sensor=esp_sensor,
        inverter=inverter,
        api_token=api_token,
        debug_level=debug_level,
    )
