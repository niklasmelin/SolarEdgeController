import solaredge_modbus
inverter=solaredge_modbus.Inverter(device="/dev/ttyUSB0", baud=9600)

inverter.connect()
inverter.connected()

inverter.read("current")
registers = inverter.read_all()

print(registers)

for register, value in registers.items():
    print(f' {register:<40} - {value}')
