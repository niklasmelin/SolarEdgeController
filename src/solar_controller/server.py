import hmac
import logging
import os
import ssl
import subprocess
from collections import deque
from datetime import datetime
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
    "last_update": 0.0,  # epoch seconds
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
    # IMPORTANT: do NOT protect /status/json, otherwise the history chart (browser JS)
    # won't be able to fetch it without leaking the token into the page.
    return path in ("/sensors", "/control")


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
    Requires OpenSSL >= 1.1.1 for '-addext'.
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
        log.info("TLS is disabled for the API server.")
        return None
    else:
        log.info("TLS is enabled for the API server.")

    certfile = Path(cfg.api_tls_certfile)
    keyfile = Path(cfg.api_tls_keyfile)

    if (not certfile.exists() or not keyfile.exists()) and cfg.api_tls_auto_generate:
        log.info("API.TLS_AUTO_GENERATE is enabled; generating self-signed cert/key.")
        _ensure_self_signed_cert(
            certfile=certfile,
            keyfile=keyfile,
            hostname=cfg.api_tls_hostname,
            ip=cfg.api_tls_ip,
            days=cfg.api_tls_days,
        )
    else:
        log.info("Using existing TLS cert/key: %s, %s", certfile, keyfile)

    if not certfile.exists() or not keyfile.exists():
        logging.error("TLS cert/key files are missing. Provide or enable API.TLS_AUTO_GENERATE in config.yaml: %s, %s", certfile, keyfile)
        raise RuntimeError(
            "TLS is enabled but cert/key files are missing. "
            "Provide API.TLS_CERTFILE/API.TLS_KEYFILE or enable API.TLS_AUTO_GENERATE."
        )

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    if hasattr(ssl, "TLSVersion"):
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2  # type: ignore[attr-defined]
    ctx.load_cert_chain(certfile=str(certfile), keyfile=str(keyfile))
    return ctx


def _format_epoch(ts: float) -> str:
    """Format epoch seconds as YYYY-MM-DD HH:MM:SS (local time)."""
    try:
        if not ts:
            return ""
        return datetime.fromtimestamp(float(ts)).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ""


# --------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------
async def handle_heartbeat(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok", "message": "Container is alive"})


async def handle_status(request: web.Request) -> web.Response:
    # Render a human-friendly last update in the initial HTML too
    last_update_formatted = _format_epoch(float(STATUS.get("last_update", 0.0) or 0.0))

    html = f"""
    <html>
    <head>
        <title>Solar Controller Status</title>
        <style>
            body {{ font-family: sans-serif; margin: 2em; }}
            h1 {{ color: #2b6cb0; }}
            table {{ border-collapse: collapse; width: 60%; margin-bottom: 2em; }}
            td, th {{ border: 1px solid #ccc; padding: 0.5em; text-align: left; }}
            td.negative_price-true {{ color: red; font-weight: bold; }}
            td.negative_price-false {{ color: green; font-weight: bold; }}
            canvas {{ max-width: 800px; max-height: 400px; }}
        </style>
    </head>
    <body>
        <h1>Solar Controller Status</h1>
        <table id="statusTable">
            <tr><th>Metric</th><th>Value</th></tr>
            <tr><td>Grid Consumption</td><td id="grid_consumption">{STATUS['grid_consumption']} W</td></tr>
            <tr><td>Home Consumption</td><td id="home_consumption">{STATUS['home_consumption']} W</td></tr>
            <tr><td>Solar Production</td><td id="solar_production">{STATUS['solar_production']} W</td></tr>
            <tr><td>New Scale Factor</td><td id="new_scale_factor">{STATUS['new_scale_factor']} %</td></tr>
            <tr><td>Current Price</td><td id="current_price">{CONTROL['current_price']}</td></tr>
            <tr>
              <td>Negative Price</td>
              <td id="negative_price" class="negative_price-{str(CONTROL['negative_price']).lower()}">{CONTROL['negative_price']}</td>
            </tr>
            <tr><td>Last Update</td><td id="last_update">{last_update_formatted}</td></tr>
        </table>

        <h2>History (last 50 cycles)</h2>
        <canvas id="historyChart"></canvas>

        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <script>
            async function fetchHistory() {{
                const res = await fetch('/status/json');
                return res.json();
            }}

            async function updateChart(chart) {{
                const data = await fetchHistory();
                const h = data.history;

                const length = (h.grid_consumption || []).length;
                chart.data.labels = Array.from({{length}}, (_, i) => i + 1);

                chart.data.datasets[0].data = h.grid_consumption || [];
                chart.data.datasets[1].data = h.home_consumption || [];
                chart.data.datasets[2].data = h.solar_production || [];
                chart.data.datasets[3].data = h.new_scale_factor || [];
                chart.update();
            }}

            async function updateTable() {{
                const data = await fetchHistory();
                const s = data.status;
                const c = data.control;

                document.getElementById('grid_consumption').innerText = s.grid_consumption + ' W';
                document.getElementById('home_consumption').innerText = s.home_consumption + ' W';
                document.getElementById('solar_production').innerText = s.solar_production + ' W';
                document.getElementById('new_scale_factor').innerText = s.new_scale_factor + ' %';
                document.getElementById('current_price').innerText = c.current_price;

                const negElem = document.getElementById('negative_price');
                negElem.innerText = c.negative_price;
                negElem.className = 'negative_price-' + c.negative_price.toString();

                // Convert Unix epoch to human-readable yyyy-mm-dd HH:MM:SS
                if (s.last_update) {{
                    const date = new Date(s.last_update * 1000);
                    const yyyy = date.getFullYear();
                    const mm = String(date.getMonth() + 1).padStart(2, '0');
                    const dd = String(date.getDate()).padStart(2, '0');
                    const HH = String(date.getHours()).padStart(2, '0');
                    const MM = String(date.getMinutes()).padStart(2, '0');
                    const SS = String(date.getSeconds()).padStart(2, '0');
                    const formatted = `${{yyyy}}-${{mm}}-${{dd}} ${{HH}}:${{MM}}:${{SS}}`;
                    document.getElementById('last_update').innerText = formatted;
                }} else {{
                    document.getElementById('last_update').innerText = '';
                }}
            }}

            const ctx = document.getElementById('historyChart').getContext('2d');
            const historyChart = new Chart(ctx, {{
                type: 'line',
                data: {{
                    labels: [],
                    datasets: [
                        {{ label: 'Grid', data: [], borderColor: 'red', fill: false }},
                        {{ label: 'Home', data: [], borderColor: 'blue', fill: false }},
                        {{ label: 'Solar', data: [], borderColor: 'green', fill: false }},
                        {{ label: 'Scale Factor', data: [], borderColor: 'orange', fill: false }},
                    ]
                }},
                options: {{ responsive: true, maintainAspectRatio: false, animation: false }}
            }});

            // Initial load
            updateChart(historyChart);
            updateTable();

            // Update every 5 seconds
            setInterval(() => {{
                updateChart(historyChart);
                updateTable();
            }}, 5000);
        </script>
    </body>
    </html>
    """
    return web.Response(text=html, content_type="text/html")


async def handle_status_json(request: web.Request) -> web.Response:
    # Note: last_update stays as epoch in JSON; the browser formats it.
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
