import numpy as np
import matplotlib.pyplot as plt
from collections import deque

# ---------------- CONFIG ----------------
PEAK_PRODUCTION_W = 10500        # Inverter max power (100%)
MIN_PRODUCTION_W = 300           # Minimum production
MAX_EXPORT_W = 200               # Maximum allowed export
MAX_DELTA_PERCENT = 15           # Max change per 10 seconds
BUFFER_SIZE = 5                  # Cyclic buffer length
SAMPLES = 60                     # 10 minutes, 10 sec intervals
LIMIT_EXPORT = True
# ---------------------------------------

# Generate sample solar production (sinusoidal-ish for variability)
time_sec = np.arange(0, SAMPLES*10, 10)
solar_production = 5000 + 5000 * np.sin(np.linspace(0, 2*np.pi, SAMPLES))  # 0-10000 W approx
solar_production = np.clip(solar_production, 0, PEAK_PRODUCTION_W)

# Generate house consumption (random between 200-8000 W)
np.random.seed(42)
house_consumption = np.random.randint(200, 8000, size=SAMPLES)

# Cyclic buffer for smoothing export
export_buffer = deque(maxlen=BUFFER_SIZE)
smoothed_export_list = []
limit_factor_list = []

last_percent = 100  # start at 100%

for i in range(SAMPLES):
    # Calculate grid export
    momentary_export = solar_production[i] - house_consumption[i]
    
    # Apply cyclic buffer moving average
    export_buffer.append(momentary_export)
    smoothed_export = sum(export_buffer)/len(export_buffer)
    smoothed_export_list.append(smoothed_export)
    
    # Compute limit factor
    if LIMIT_EXPORT:
        # Compute minimum production percent
        min_percent = (MIN_PRODUCTION_W / PEAK_PRODUCTION_W) * 100
        # Desired percent to limit export
        desired_percent = max(
            min_percent,
            100 - ((smoothed_export - MAX_EXPORT_W)/PEAK_PRODUCTION_W*100)
        )
        # Rate limit
        delta = desired_percent - last_percent
        if delta > MAX_DELTA_PERCENT:
            desired_percent = last_percent + MAX_DELTA_PERCENT
        elif delta < -MAX_DELTA_PERCENT:
            desired_percent = last_percent - MAX_DELTA_PERCENT
        # Clamp
        desired_percent = max(min_percent, min(100, desired_percent))
        last_percent = desired_percent
    else:
        desired_percent = 100
        
    limit_factor_list.append(desired_percent)

# Compute limited production (for visualization)
limited_production = np.array(solar_production) * np.array(limit_factor_list)/100
grid_export = limited_production - house_consumption

# ---------------- PLOT ----------------
plt.figure(figsize=(15,8))
plt.plot(time_sec/60, solar_production, label="Solar Production [W]", color="gold")
plt.plot(time_sec/60, house_consumption, label="House Consumption [W]", color="orange")
plt.plot(time_sec/60, smoothed_export_list, label="Smoothed Grid Export [W]", color="red", linestyle='--')
plt.plot(time_sec/60, grid_export, label="Limited Grid Export [W]", color="green")
plt.plot(time_sec/60, np.array(limit_factor_list)/100*PEAK_PRODUCTION_W, 
         label="Production Limit Factor [% of peak]", color="blue", linestyle=':')
plt.xlabel("Time [minutes]")
plt.ylabel("Power [W]")
plt.title("Export Limiter Simulation")
plt.legend()
plt.grid(True)
plt.show()
