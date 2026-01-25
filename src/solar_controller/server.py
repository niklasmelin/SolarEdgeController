import logging
import time
from collections import deque
from aiohttp import web
from solar_controller.config import AppConfig

log = logging.getLogger(__name__)
HEARTBEAT_PORT = 8080

# --------------------------------------------------------------------
# Shared state
# --------------------------------------------------------------------
STATUS: dict[str, float] = {
    "grid_consumption": 0.0,
    "home_consumption": 0.0,
    "solar_production": 0.0,
    "new_scale_factor": 0.0,
    "last_update": 0.0
}

HISTORY: dict[str, deque] = {
    "grid_consumption": deque(maxlen=50),
    "home_consumption": deque(maxlen=50),
    "solar_production": deque(maxlen=50),
    "new_scale_factor": deque(maxlen=50),
}

CONTROL: dict[str, float | bool] = {
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
            <tr><td>Negative Price</td><td id="negative_price" class="negative_price-{str(CONTROL['negative_price']).lower()}">{CONTROL['negative_price']}</td></tr>
            <tr><td>Last Update</td><td id="last_update">{STATUS.get('last_update', '')}</td></tr>
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
                const length = h.grid_consumption.length;
                chart.data.labels = Array.from({{length}}, (_, i) => i + 1);
                chart.data.datasets[0].data = h.grid_consumption;
                chart.data.datasets[1].data = h.home_consumption;
                chart.data.datasets[2].data = h.solar_production;
                chart.data.datasets[3].data = h.new_scale_factor;
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
                const date = new Date(s.last_update * 1000);
                const yyyy = date.getFullYear();
                const mm = String(date.getMonth() + 1).padStart(2, '0');
                const dd = String(date.getDate()).padStart(2, '0');
                const HH = String(date.getHours()).padStart(2, '0');
                const MM = String(date.getMinutes()).padStart(2, '0');
                const SS = String(date.getSeconds()).padStart(2, '0');
                const formatted = `${{yyyy}}-${{mm}}-${{dd}} ${{HH}}:${{MM}}:${{SS}}`;
                document.getElementById('last_update').innerText = formatted;
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

# --------------------------------------------------------------------
# JSON history
# --------------------------------------------------------------------
async def handle_status_json(request):
    return web.json_response({
        "status": dict(STATUS),
        "history": {k: list(v) for k, v in HISTORY.items()},
        "control": dict(CONTROL)
    })

# --------------------------------------------------------------------
# Control endpoint
# --------------------------------------------------------------------
async def handle_control(request):
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
    inverter = request.app.get("inverter")
    if inverter is None:
        return web.json_response({"error": "Inverter not available"}, status=500)
    try:
        sensors = inverter.get_ha_sensors()
        return web.json_response(sensors)
    except Exception as e:
        log.exception("Failed to get HA sensors: %s", e)
        return web.json_response({"error": str(e)}, status=500)

# --------------------------------------------------------------------
# Start server
# --------------------------------------------------------------------
async def start_server(config: AppConfig, inverter=None):
    app = web.Application()
    app["config"] = config
    app["inverter"] = inverter

    app.router.add_get("/health", handle_heartbeat)
    app.router.add_get("/status", handle_status)
    app.router.add_get("/status/json", handle_status_json)
    app.router.add_post("/control", handle_control)
    app.router.add_get("/sensors", handle_sensors)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", HEARTBEAT_PORT)
    await site.start()
    log.info("HTTP server running on port %d", HEARTBEAT_PORT)
