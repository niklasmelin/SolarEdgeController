import solaredge_modbus

class SolarEdgeInverter(solaredge_modbus.Inverter):
    def __init__(self):
        # Initialize all values from the example data (except scale factors)
        self.c_id = None
        self.c_did = None
        self.c_length = None
        self.c_manufacturer = None
        self.c_model = None
        self.c_version = None
        self.c_serialnumber = None
        self.c_deviceaddress = None
        self.c_sunspec_did = None
        self.c_sunspec_length = None
        self.current = None
        self.l1_current = None
        self.l2_current = None
        self.l3_current = None
        self.l1_voltage = None
        self.l2_voltage = None
        self.l3_voltage = None
        self.l1n_voltage = None
        self.l2n_voltage = None
        self.l3n_voltage = None
        self.power_ac = None
        self.frequency = None
        self.power_apparent = None
        self.power_reactive = None
        self.power_factor = None
        self.energy_total = None
        self.current_dc = None
        self.voltage_dc = None
        self.power_dc = None
        self.temperature = None
        self.status = None
        self.vendor_status = None
        self.rrcr_state = None
        self.active_power_limit = None
        self.cosphi = None
        self.commit_power_control_settings = None
        self.restore_power_control_default_settings = None
        self.reactive_power_config = None
        self.reactive_power_response_time = None
        self.advanced_power_control_enable = None
        self.export_control_mode = None
        self.export_control_limit_mode = None
        self.export_control_site_limit = None

    def read_inverter(self, device="/dev/ttyUSB0", baud=9600):
        """
        Connects to the inverter, reads all registers, applies scaling factors, 
        and stores the scaled data in the class attributes.
        """
        # Initialize the connection
        super().__init__(device=device, baud=baud)
        self.connect()

        if not self.connected():
            raise ConnectionError("Failed to connect to the inverter.")

        # Read all registers
        registers = self.read_all()

        # Apply scaling factors and store the scaled data
        for key, value in registers.items():
            scale_key = f"{key}_scale"
            if scale_key in registers:
                scaled_value = float(value) * (10 ** int(registers[scale_key]))
            else:
                scaled_value = value

            # Store the scaled value in the corresponding attribute
            if hasattr(self, key):
                setattr(self, key, scaled_value)

        # Disconnect after reading
        self.disconnect()

    def print_inverter_data(self):
        """
        Prints all the inverter data stored in the class attributes.
        """
        print("Inverter Data: \n\tAttribute           : Value")
        for attribute in dir(self):
            if attribute.startswith("c_") and not callable(getattr(self, attribute)):
                value = getattr(self, attribute)
                print(f"\t{attribute:<20}: {value}")
        print("\n")
              

    def print_status(self):
        """
        Prints the current status of the inverter.
        """
        print(f"Status: {self.status}: {self.registers["status"][6][self.status]}" )
        print(f"Vendor Status: {self.vendor_status}", self.registers["vendor_status"] )
        print(f"RRC State: {self.rrcr_state}", self.registers["rrcr_state"])
        print(f"Active Power Limit: {self.active_power_limit}", self.registers["active_power_limit"])
        print(f"Cosphi: {self.cosphi}", self.registers["cosphi"])
        print(f"Export Control Mode: {self.export_control_mode}", self.registers["export_control_mode"])
        print(f"Export Control Limit Mode: {self.export_control_limit_mode}", self.registers["export_control_limit_mode"])
        print(f"Export Control Site Limit: {self.export_control_site_limit}", self.registers["export_control_site_limit"])