from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any, Optional

import confuse


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
    # Existing
    esp_sensor: ESPSensorConfig
    inverter: InverterConfig
    api_token: str
    debug_level: str

    # New: API server settings
    api_host: str = "0.0.0.0"
    api_port: int = 8080

    # New: TLS settings
    api_tls_enabled: bool = False
    api_tls_certfile: str = "certs/server.crt"
    api_tls_keyfile: str = "certs/server.key"
    api_tls_auto_generate: bool = True
    api_tls_hostname: str = "solaredgecontroller"
    api_tls_ip: Optional[str] = None
    api_tls_days: int = 3650


def _cfg_get(cfg: confuse.Configuration, path: list[str], typ: Any, default: Any) -> Any:
    node = cfg
    try:
        for key in path:
            node = node[key]
        return node.get(typ)
    except Exception:
        return default


def load_config(config_file: str = "config.yaml") -> AppConfig:
    cfg = confuse.Configuration("solar_controller", __name__)
    cfg.set_file(config_file)

    esp_sensor = ESPSensorConfig(
        reader_host=_cfg_get(cfg, ["ESP_SENSOR", "ESP_READER_HOST"], str, "127.0.0.1"),
        reader_port=_cfg_get(cfg, ["ESP_SENSOR", "ESP_READER_PORT"], int, 6053),
        encryption_key=_cfg_get(cfg, ["ESP_SENSOR", "ESP_READER_ENCRYPTION_KEY"], str, ""),
        window_seconds=_cfg_get(cfg, ["ESP_SENSOR", "ESP_READER_WINDOW_SECONDS"], float, 0.5),
    )

    inverter = InverterConfig(
        device=_cfg_get(cfg, ["INVERTER", "SOLAR_EDGE_INVERTER_DEVICE"], str, "/dev/ttyUSB0"),
        baud=_cfg_get(cfg, ["INVERTER", "SOLAR_EDGE_INVERTER_BAUD"], int, 9600),
        timeout=_cfg_get(cfg, ["INVERTER", "SOLAR_EDGE_INVERTER_TIMEOUT"], int, 2),
    )

    api_token = _cfg_get(cfg, ["API", "TOKEN"], str, "")
    debug_level = _cfg_get(cfg, ["DEBUG_LEVEL"], str, "INFO")

    api_host = _cfg_get(cfg, ["API", "HOST"], str, "0.0.0.0")
    api_port = _cfg_get(cfg, ["API", "PORT"], int, 8080)

    api_tls_enabled = _cfg_get(cfg, ["API", "TLS_ENABLED"], bool, False)
    api_tls_certfile = _cfg_get(cfg, ["API", "TLS_CERTFILE"], str, "certs/server.crt")
    api_tls_keyfile = _cfg_get(cfg, ["API", "TLS_KEYFILE"], str, "certs/server.key")
    api_tls_auto_generate = _cfg_get(cfg, ["API", "TLS_AUTO_GENERATE"], bool, True)
    api_tls_hostname = _cfg_get(cfg, ["API", "TLS_HOSTNAME"], str, "solaredgecontroller")
    api_tls_ip = _cfg_get(cfg, ["API", "TLS_IP"], str, None)
    api_tls_days = _cfg_get(cfg, ["API", "TLS_DAYS"], int, 3650)

    # --- Configure logging here ---
    log_level = getattr(logging, debug_level.upper(), logging.INFO)
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    if not root_logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)

    logging.getLogger("aiohttp.access").setLevel(logging.WARNING)
    logging.getLogger("pymodbus").setLevel(logging.WARNING)
    logging.getLogger("aioesphomeapi.connection").setLevel(logging.WARNING)

    logging.info("Logger configured with level %s", debug_level.upper())

    return AppConfig(
        esp_sensor=esp_sensor,
        inverter=inverter,
        api_token=api_token,
        debug_level=debug_level,
        api_host=api_host,
        api_port=api_port,
        api_tls_enabled=api_tls_enabled,
        api_tls_certfile=api_tls_certfile,
        api_tls_keyfile=api_tls_keyfile,
        api_tls_auto_generate=api_tls_auto_generate,
        api_tls_hostname=api_tls_hostname,
        api_tls_ip=api_tls_ip,
        api_tls_days=api_tls_days,
    )
