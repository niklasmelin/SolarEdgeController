import hmac
import logging
import os
import ssl
import subprocess
import time
from collections import deque
from pathlib import Path
from typing import Deque, Dict, Optional

from aiohttp import web

from solar_controller.config import AppConfig

log = logging.getLogger(__name__)


# --------------------------------------------------------------------
# Shared state (used by your control loop / status page)
# --------------------------------------------------------------------
STATUS: Dict[str, float] = {
    "grid_consumption": 0.0,
    "home_consumption": 0.0,
    "solar_production": 0.0,
    "new_scale_factor": 0.0,
    "last_update": 0.0,
}

HISTORY: Dict[str, Deque[float]] = {
    "grid_consumption": deque(maxlen=50),
    "home_consumption": deque(maxlen=50),
    "solar_production": deque(maxlen=50),
    "new_scale_factor": deque(maxlen=50),
}

CONTROL: Dict[str, float | bool] = {
    "current_price": 0.0,
    "negative_price": False,
}


# --------------------------------------------------------------------
# Auth / TLS helpers
# --------------------------------------------------------------------
def _extract_bearer_token(auth_header: str) -> Optional[str]:
    """Parse 'Authorization: Bearer <token>'."""
    if not auth_header:
        return None
    parts = auth_header.split(None, 1)
    if len(parts) != 2:
        return None
    scheme, token = parts[0].lower(), parts[1].strip()
    if scheme != "bearer" or not token:
        return None
    return token


def _require_auth_for_path(path: str) -> bool:
    return path in ("/sensors", "/control", "/status/json")


@web.middleware
async def auth_middleware(request: web.Request, handler):
    cfg: AppConfig = request.app["config"]
    if cfg.api_token and _require_auth_for_path(request.path):
        presented = _extract_bearer_token(request.headers.get("Authorization", ""))
        if presented is None or not hmac.compare_digest(presented, cfg.api_token):
            return web.json_response({"error": "unauthorized"}, status=401)
    return await handler(request)


def _ensure_self_signed_cert(
    *,
    certfile: Path,
    keyfile: Path,
    hostname: str,
    ip: Optional[str],
    days: int = 3650,
) -> None:
    """
    Generate a self-signed certificate using the local 'openssl' binary.

    NOTE: Requires openssl >= 1.1.1 for '-addext'.
    """
    certfile.parent.mkdir(parents=True, exist_ok=True)

    san_parts = [f"DNS:{hostname}"]
    if ip:
        san_parts.append(f"IP:{ip}")
    san = ",".join(san_parts)

    cmd = [
        "openssl",
        "req",
        "-x509",
        "-newkey",
        "rsa:2048",
        "-nodes",
        "-keyout",
        str(keyfile),
        "-out",
        str(certfile),
        "-days",
        str(days),
        "-subj",
        f"/CN={hostname}",
        "-addext",
        f"subjectAltName={san}",
    ]

    log.warning("Generating self-signed TLS certificate: %s", certfile)
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    try:
        os.chmod(keyfile, 0o600)
    except Exception:
        pass


def build_ssl_context(cfg: AppConfig) -> Optional[ssl.SSLContext]:
    """Return SSLContext if TLS is enabled; otherwise None."""
    if not cfg.api_tls_enabled:
        return None

    certfile = Path(cfg.api_tls_certfile)
    keyfile = Path(cfg.api_tls_keyfile)

    if (not certfile.exists() or not keyfile.exists()) and cfg.api_tls_auto_generate:
        logging.info("Auto-generating self-signed TLS certificate/key")
        _ensure_self_signed_cert(
            certfile=certfile,
            keyfile=keyfile,
            hostname=cfg.api_tls_hostname,
            ip=cfg.api_tls_ip,
            days=cfg.api_tls_days,
        )

    if not certfile.exists() or not keyfile.exists():
        logging.error("TLS cert/key files are missing: %s, %s", certfile, keyfile)
        raise RuntimeError(
            "TLS is enabled but cert/key files are missing. "
            "Provide API.TLS_CERTFILE/API.TLS_KEYFILE or enable API.TLS_AUTO_GENERATE."
        )

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    if hasattr(ssl, "TLSVersion"):
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2  # type: ignore[attr-defined]
    ctx.load_cert_chain(certfile=str(certfile), keyfile=str(keyfile))
    return ctx


# --------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------
async def handle_heartbeat(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok", "message": "Container is alive"})


async def handle_status(request: web.Request) -> web.Response:
    html = f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Solar Controller Status</title></head>
<body>
<h1>Solar Controller Status</h1>
<table border="1" cellpadding="6">
  <tr><th>Metric</th><th>Value</th></tr>
  <tr><td>Grid Consumption</td><td>{STATUS['grid_consumption']} W</td></tr>
  <tr><td>Home Consumption</td><td>{STATUS['home_consumption']} W</td></tr>
  <tr><td>Solar Production</td><td>{STATUS['solar_production']} W</td></tr>
  <tr><td>New Scale Factor</td><td>{STATUS['new_scale_factor']} %</td></tr>
  <tr><td>Current Price</td><td>{CONTROL['current_price']}</td></tr>
  <tr><td>Negative Price</td><td>{CONTROL['negative_price']}</td></tr>
  <tr><td>Last Update</td><td>{STATUS.get('last_update', '')}</td></tr>
</table>

<h2>History (last 50 cycles)</h2>
<pre>{ {k: list(v) for k, v in HISTORY.items()} }</pre>
</body>
</html>
"""
    return web.Response(text=html, content_type="text/html")


async def handle_status_json(request: web.Request) -> web.Response:
    return web.json_response(
        {
            "status": dict(STATUS),
            "history": {k: list(v) for k, v in HISTORY.items()},
            "control": dict(CONTROL),
        }
    )


async def handle_control(request: web.Request) -> web.Response:
    """
    Payload example:
      {"current_price": 1.23, "negative_price": false}
    """
    try:
        data = await request.json()
        for key in ("current_price", "negative_price"):
            if key in data:
                CONTROL[key] = data[key]
        return web.json_response({"status": "ok", "updated": CONTROL})
    except Exception as exc:
        return web.json_response({"error": str(exc)}, status=400)


async def handle_sensors(request: web.Request) -> web.Response:
    """
    Returns 503 if inverter identity (serial) is not ready yet, to prevent
    Home Assistant from creating entities with unstable unique_ids.
    """
    inverter = request.app.get("inverter")
    if inverter is None:
        return web.json_response({"error": "Inverter not available"}, status=500)

    try:
        sensors = inverter.get_ha_sensors()
        return web.json_response(sensors)
    except RuntimeError as exc:
        return web.json_response({"error": str(exc)}, status=503)
    except Exception as exc:
        log.exception("Failed to get HA sensors: %s", exc)
        return web.json_response({"error": str(exc)}, status=500)


# --------------------------------------------------------------------
# Start server
# --------------------------------------------------------------------
async def start_server(config: AppConfig, inverter=None) -> None:
    # Best-effort: initialize inverter identity once before HA hits /sensors.
    if inverter is not None and hasattr(inverter, "update_identity_registers"):
        try:
            await inverter.update_identity_registers()
        except Exception as exc:
            log.error("Inverter identity not ready: %s", exc)

    app = web.Application(middlewares=[auth_middleware])
    app["config"] = config
    app["inverter"] = inverter

    app.router.add_get("/health", handle_heartbeat)
    app.router.add_get("/status", handle_status)
    app.router.add_get("/status/json", handle_status_json)
    app.router.add_post("/control", handle_control)
    app.router.add_get("/sensors", handle_sensors)

    runner = web.AppRunner(app)
    await runner.setup()

    ssl_ctx = build_ssl_context(config)

    site = web.TCPSite(
        runner,
        host=config.api_host,
        port=config.api_port,
        ssl_context=ssl_ctx,
    )
    await site.start()

    scheme = "https" if ssl_ctx else "http"
    log.info("Server running on %s://%s:%d", scheme, config.api_host, config.api_port)
