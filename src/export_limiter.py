import asyncio
import time
from collections import deque

from src.EspReader import EspReader
from src.SolarEdgeInverter import SolarEdgeInverter
from src.solaredge_modbus import inverterStatus

# --------------------- CONFIG ---------------------
PEAK_PRODUCTION_W = 10500        # 100%
MIN_PRODUCTION_W = 300           # Don't reduce below this
MAX_EXPORT_W = 200               # Maximum allowed export
MAX_DELTA_PERCENT = 15           # Max change per 10 seconds
BUFFER_SIZE = 5                   # Moving average length
READ_INTERVAL = 10                # seconds
LIMIT_EXPORT = True               # Enable/disable export limiting

# Initialize ESP reader
reader = EspReader(
    host="192.168.30.182",
    port=6053,
    encryption_key="abc..123abc..123abc..123abc..123abc..123"
)

# Initialize inverter
inverter = SolarEdgeInverter(
    device="/dev/ttyUSB0",
    baud=9600,
    timeout=2
)

# Cyclic buffer for smoothing export measurements
export_buffer = deque(maxlen=BUFFER_SIZE)

# Last applied production percent
last_percent = 100

# --------------------------------------------------


def update_smoothed_export(momentary_export: float) -> float:
    """
    Update the cyclic buffer with a new measurement
    and return the smoothed value (moving average).
    """
    export_buffer.append(momentary_export)
    return sum(export_buffer) / len(export_buffer)


async def limit_export_loop():
    global last_percent

    await reader.ensure_connected()
    await inverter.check_connection()

    while True:
        # Get current export
        data = reader.get_data_as_json()
        raw_export = data.get("momentary_active_export", 0)
        smoothed_export = update_smoothed_export(raw_export)

        # Only adjust if limiting is enabled
        if LIMIT_EXPORT:
            # Read inverter state
            inverter_status = inverter.status
            power_ac = inverter.power_ac or 0

            # Check production conditions
            if inverter_status == inverterStatus.I_STATUS_MPPT.value and power_ac > MIN_PRODUCTION_W:
                # Compute minimum production in %
                min_percent = (MIN_PRODUCTION_W / PEAK_PRODUCTION_W) * 100

                # Desired percent to achieve max export
                desired_percent = max(
                    min_percent,
                    100 - ((smoothed_export - MAX_EXPORT_W) / PEAK_PRODUCTION_W * 100)
                )

                # Apply rate limiting
                delta = desired_percent - last_percent
                if delta > MAX_DELTA_PERCENT:
                    desired_percent = last_percent + MAX_DELTA_PERCENT
                elif delta < -MAX_DELTA_PERCENT:
                    desired_percent = last_percent - MAX_DELTA_PERCENT

                # Clamp to min/max
                desired_percent = max(min_percent, min(100, desired_percent))

                # Apply to inverter
                await inverter.set_production_limit(int(desired_percent))
                last_percent = desired_percent

                print(
                    f"[{time.strftime('%H:%M:%S')}] "
                    f"Export: {smoothed_export:.0f} W, "
                    f"Power AC: {power_ac:.0f} W, "
                    f"Production Limit: {int(desired_percent)}%"
                )
            else:
                print(
                    f"[{time.strftime('%H:%M:%S')}] Inverter not producing or below min power."
                )

        # Wait before next reading
        await asyncio.sleep(READ_INTERVAL)


if __name__ == "__main__":
    try:
        asyncio.run(limit_export_loop())
    except KeyboardInterrupt:
        print("\nExport limiter stopped by user.")
