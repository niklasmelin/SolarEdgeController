import time
import random
from src.SolarEdgeInverter import SolarEdgeInverter

se_inverter = SolarEdgeInverter(device="/dev/ttyUSB0", baud=9600, timeout=2)
se_inverter.print_inverter_data()
se_inverter.print_all()

print(f"\n\nRegister commit_power_control_settings: {se_inverter.read('commit_power_control_settings')}")

limit = random.randint(10,90)

print(f"\nSet active power limit to {limit}%")
se_inverter.set_production_limit(limit)

now = time.time()
for i in range(8):
    print(f" After setting production limit to {limit} % and {time.time() - now}s wait")
    print(f"   Register commit_power_control_settings: {se_inverter.read('commit_power_control_settings')}")
    print(f"   Register active_power_limit: {se_inverter.read('active_power_limit')}")

print(f"\nSet active power limit to 100%")
se_inverter.set_restore_power_control_defaults()

limit = 100
for i in range(8):
    print(f" After setting production limit to {limit} % and {time.time()-now}s wait")
    print(f"   Register commit_power_control_settings: {se_inverter.read('commit_power_control_settings')}")
    print(f"   Register active_power_limit: {se_inverter.read('active_power_limit')}")


# Set limit multiple times

for i in range(4):
    limit = random.randint(10,90)
    print(f"\nSet active power limit to {limit}%")
    se_inverter.set_production_limit(limit)    
    print(f" After setting production limit to {limit} % and {time.time()-now}s wait")
    print(f"   Register commit_power_control_settings: {se_inverter.read('commit_power_control_settings')}")
    print(f"   Register active_power_limit: {se_inverter.read('active_power_limit')}")
    time.sleep(2)


print(f"\nSet active power limit to 100%")
se_inverter.set_restore_power_control_defaults()
print(f" After setting production limit to 100% -  {se_inverter.read('active_power_limit')}")
time.sleep(1)
print(f" After setting production limit to 100% -  {se_inverter.read('active_power_limit')}")
print(f"   Register commit_power_control_settings: {se_inverter.read('commit_power_control_settings')}")
print(f" After setting production limit to 100% -  {se_inverter.read('active_power_limit')}")
time.sleep(8)
print(f" 8 - After setting production limit to 100% -  {se_inverter.read('active_power_limit')}")



se_inverter._read_inverter_all()
se_inverter.print_all()



total_time = 0
currents = ["current", "l1_current", "l2_current", "l3_current","l1_voltage", "l2_voltage", "l3_voltage", "l1n_voltage", "l2n_voltage", "l3n_voltage"]
for i in range(1):
    now = time.time()
    a = []
    for register in currents:
        a.append(se_inverter.read(register))
    
    cycle =  time.time()-now
    total_time += cycle
    
    print(a,cycle, cycle/len(currents), total_time)
