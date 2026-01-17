import asyncio
import logging
from aiohttp import web

log = logging.getLogger(__name__)

HEARTBEAT_PORT = 8080

# Shared state dictionary to hold current values
# Other modules can update these values
STATUS = {
    "grid_consumption": 0,
    "home_consumption": 0,
    "solar_production": 0,
    "new_scale_factor": 0,
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
    """Serve a simple HTML page showing current values."""
    html = f"""
    <html>
        <head>
            <title>Solar Controller Status</title>
            <style>
                body {{ font-family: sans-serif; margin: 2em; }}
                h1 {{ color: #2b6cb0; }}
                table {{ border-collapse: collapse; width: 50%; }}
                td, th {{ border: 1px solid #ccc; padding: 0.5em; text-align: left; }}
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
        </body>
    </html>
    """
    return web.Response(text=html, content_type="text/html")

# --------------------------------------------------------------------
# Start aiohttp server
# --------------------------------------------------------------------
async def start_server():
    """Start the aiohttp server with /health and /status endpoints."""
    app = web.Application()
    app.router.add_get("/health", handle_heartbeat)
    app.router.add_get("/status", handle_status)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", HEARTBEAT_PORT)
    await site.start()
    log.info("HTTP server running on port %d", HEARTBEAT_PORT)
