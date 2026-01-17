from dataclasses import dataclass
from pathlib import Path
import confuse
import logging
import os
import sys

log = logging.getLogger(__name__)
in_docker = os.getenv("DOCKER") == "True"

if in_docker:
    log.info("Running inside Docker container.")


@dataclass(frozen=True)
class ESPSensorConfig:
    reader_host: str
    reader_port: int
    encryption_key: str
    window_seconds: float


@dataclass(frozen=True)
class InverterConfig:
    device: str
    baud: int
    timeout: int


@dataclass(frozen=True)
class AppConfig:
    esp_sensor: ESPSensorConfig
    inverter: InverterConfig


def load_config(config_path: str | None = None) -> AppConfig:
    """
    Load application configuration.

    If no path is provided, defaults to ./config.yaml.
    """
    if config_path is None:
        config_file = Path.cwd() / "config.yaml"
    else:
        config_file = Path(config_path)

    if not config_file.exists() and not in_docker:
        raise FileNotFoundError(f"Config file not found: {config_file}")
    elif not config_file.exists() and in_docker:
        log.error(
            "Config file %s not found. Using default config path /app/config.yaml in Docker.",
            config_file,
        )
        sys.exit(1)

    cfg = confuse.Configuration("solar_controller", __name__)
    cfg.set_file(str(config_file))

    log.info("Loaded configuration from %s", config_file.resolve())

    return AppConfig(
        esp_sensor=ESPSensorConfig(
            reader_host=cfg["ESP_SENSOR"]["ESP_READER_HOST"].get(str),
            reader_port=cfg["ESP_SENSOR"]["ESP_READER_PORT"].get(int),
            encryption_key=cfg["ESP_SENSOR"]["ESP_READER_ENCRYPTION_KEY"].get(str),
            window_seconds=cfg["ESP_SENSOR"]["ESP_READER_WINDOW_SECONDS"].get(float),
        ),
        inverter=InverterConfig(
            device=cfg["INVERTER"]["SOLAR_EDGE_INVERTER_DEVICE"].get(str),
            baud=cfg["INVERTER"]["SOLAR_EDGE_INVERTER_BAUD"].get(int),
            timeout=cfg["INVERTER"]["SOLAR_EDGE_INVERTER_TIMEOUT"].get(int),
        ),
    )
