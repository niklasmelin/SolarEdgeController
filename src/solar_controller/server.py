# src/solar_controller/server.py
import asyncio
import logging
from collections import deque
from aiohttp import web

log = logging.getLogger(__name__)

HEARTBEAT_PORT = 8080

# --------------------------------------------------------------------
# Shared state
# --------------------------------------------------------------------
STATUS = {
    "grid_consumption": 0,
    "home_consumption": 0,
    "solar_production": 0,
    "new_scale_factor": 0,
}

# Keep history of last 50 cycles for graphing
HISTORY_LENGTH = 50
HISTORY = {
    "grid_consumption": deque(maxlen=HISTORY_LENGTH),
    "home_consumption": deque(maxlen=HISTORY_LENGTH),
    "solar_production": deque(maxlen=HISTORY_LENGTH),
    "new_scale_factor": deque(maxlen=HISTORY_LENGTH),
}

# --------------------------------------------------------------------
# Heartbeat endpoint
# --------------------------------------------------------------------
async def handle_heartbeat(request):
    """Health check endpoint for container monitoring."""
    return web.json_response({"status": "ok", "message": "Container is alive"})

# --------------------------------------------------------------------
# Status webpage endpoint
# --------------------------------------------------------------------
async def handle_status(request):
    """Serve a simple HTML page showing current values and history graph."""
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

            <h2>History (last {HISTORY_LENGTH} values)</h2>
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
                            {{ label: 'Grid [W]', data: [], borderColor: 'red', fill: false }},
                            {{ label: 'Home [W]', data: [], borderColor: 'blue', fill: false }},
                            {{ label: 'Solar [W]', data: [], borderColor: 'green', fill: false }},
                            {{ label: 'Scale Factor [%]', data: [], borderColor: 'orange', fill: false }},
                        ]
                    }},
                    options: {{
                        responsive: true,
                        maintainAspectRatio: false,
                        animation: false
                    }}
                }});

                // Update every 5 seconds
                setInterval(() => updateChart(historyChart), 5000);
                updateChart(historyChart);
            </script>
        </body>
    </html>
    """
    return web.Response(text=html, content_type="text/html")

# --------------------------------------------------------------------
# JSON history endpoint
# --------------------------------------------------------------------
async def handle_status_json(request):
    """Return the last 50 values as JSON for charting."""
    data = {k: list(v) for k, v in HISTORY.items()}
    return web.json_response(data)

# --------------------------------------------------------------------
# Start aiohttp server
# --------------------------------------------------------------------
async def start_server():
    """Start the aiohttp server with /health, /status, and /status/json endpoints."""
    app = web.Application()
    app.router.add_get("/health", handle_heartbeat)
    app.router.add_get("/status", handle_status)
    app.router.add_get("/status/json", handle_status_json)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", HEARTBEAT_PORT)
    await site.start()
    log.info("HTTP server running on port %d", HEARTBEAT_PORT)
