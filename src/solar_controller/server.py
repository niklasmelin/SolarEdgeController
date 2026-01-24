import logging
from collections import deque
from aiohttp import web
from solar_controller.config import AppConfig

log = logging.getLogger(__name__)
HEARTBEAT_PORT = 8080

# Shared state
STATUS = {
    "grid_consumption": 0,
    "home_consumption": 0,
    "solar_production": 0,
    "new_scale_factor": 0,
}

HISTORY = {
    "grid_consumption": deque(maxlen=50),
    "home_consumption": deque(maxlen=50),
    "solar_production": deque(maxlen=50),
    "new_scale_factor": deque(maxlen=50),
}

CONTROL = {
    "current_price": 0.0,
    "negative_price": False,
}

# --------------------------------------------------------------------
# Health / heartbeat
# --------------------------------------------------------------------
async def handle_heartbeat(request):
    return web.json_response({"status": "ok", "message": "Container is alive"})

# --------------------------------------------------------------------
# Status page
# --------------------------------------------------------------------
async def handle_status(request):
    html = f"""
    <html>
    <head>
        <title>Solar Controller Status</title>
        <style>
            body {{ font-family: sans-serif; margin: 2em; }}
            h1 {{ color: #2b6cb0; }}
            table {{ border-collapse: collapse; width: 50%; margin-bottom: 2em; }}
            td, th {{ border: 1px solid #ccc; padding: 0.5em; text-align: left; }}
            canvas {{ max-width: 800px; max-height: 400px; }}
        </style>
    </head>
    <body>
        <h1>Solar Controller Status</h1>
        <table>
            <tr><th>Metric</th><th>Value</th></tr>
            <tr><td>Grid Consumption</td><td>{STATUS['grid_consumption']} W</td></tr>
            <tr><td>Home Consumption</td><td>{STATUS['home_consumption']} W</td></tr>
            <tr><td>Solar Production</td><td>{STATUS['solar_production']} W</td></tr>
            <tr><td>New Scale Factor</td><td>{STATUS['new_scale_factor']} %</td></tr>
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
                const length = data.grid_consumption.length;
                chart.data.labels = Array.from({{length}}, (_, i) => i+1);
                chart.data.datasets[0].data = data.grid_consumption;
                chart.data.datasets[1].data = data.home_consumption;
                chart.data.datasets[2].data = data.solar_production;
                chart.data.datasets[3].data = data.new_scale_factor;
                chart.update();
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
            setInterval(() => updateChart(historyChart), 5000);
            updateChart(historyChart);
        </script>
    </body>
    </html>
    """
    return web.Response(text=html, content_type="text/html")

# --------------------------------------------------------------------
# JSON history
# --------------------------------------------------------------------
async def handle_status_json(request):
    return web.json_response({k: list(v) for k, v in HISTORY.items()})

# --------------------------------------------------------------------
# Control endpoint with token
# --------------------------------------------------------------------
async def handle_control(request):
    # cfg: AppConfig = request.app["config"]
    # token = request.headers.get("Authorization")
    # if not token or token != f"Bearer {cfg.api_token}":
    #    return web.json_response({"error": "Unauthorized"}, status=401)

    try:
        data = await request.json()
        for key in ["current_price", "negative_price"]:
            if key in data:
                CONTROL[key] = data[key]
        return web.json_response({"status": "ok", "updated": CONTROL})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=400)

# --------------------------------------------------------------------
# HA Sensors endpoint
# --------------------------------------------------------------------
async def handle_sensors(request):
    """
    Expose inverter sensors for Home Assistant.
    Calls inverter.get_ha_sensors() and returns a JSON array.
    """
    inverter = request.app.get("inverter")
    if inverter is None:
        return web.json_response({"error": "Inverter not available"}, status=500)
    
    try:
        sensors = inverter.get_ha_sensors()
        return web.json_response(sensors)
    except Exception as e:
        log.exception("Failed to get HA sensors: %s", e)

# --------------------------------------------------------------------
# Start server
# --------------------------------------------------------------------
async def start_server(config: AppConfig, inverter=None):
    """Start aiohttp server with /health, /status, /status/json, /control and /sensors endpoints"""
    app = web.Application()
    app["config"] = config
    app["inverter"] = inverter  # Pass inverter instance for /sensors

    # Existing routes
    app.router.add_get("/health", handle_heartbeat)
    app.router.add_get("/status", handle_status)
    app.router.add_get("/status/json", handle_status_json)
    app.router.add_post("/control", handle_control)

    # New HA sensors route
    app.router.add_get("/sensors", handle_sensors)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", HEARTBEAT_PORT)
    await site.start()
    log.info("HTTP server running on port %d", HEARTBEAT_PORT)
