import logging
import solaredge_modbus

# Configure the logger
logging.basicConfig(
    level=logging.INFO,  # Set the default logging level
    format="%(asctime)s - %(levelname)s - %(name)s - %(funcName)s - %(message)s",  # Log format
    datefmt="%Y-%m-%d %H:%M:%S"  # Date format
)

# Create a logger instance
logger = logging.getLogger("SolarEdgeLogger")

REGISTER_SCALE_FACTORS = {
    "current": "current_scale",
    "l1_current": "current_scale",
    "l2_current": "current_scale",
    "l3_current": "current_scale",
    "l1_voltage": "voltage_scale",
    "l2_voltage": "voltage_scale",
    "l3_voltage": "voltage_scale",
    "l1n_voltage": "voltage_scale",
    "l2n_voltage": "voltage_scale",
    "l3n_voltage": "voltage_scale",
    "power_ac": "power_ac_scale",
    "frequency": "frequency_scale",
    "power_apparent": "power_apparent_scale",
    "power_reactive": "power_reactive_scale",
    "power_factor": "power_factor_scale",
    "energy_total": "energy_total_scale",
    "current_dc": "current_dc_scale",
    "voltage_dc": "voltage_dc_scale",
    "power_dc": "power_dc_scale",
    "temperature": "temperature_scale"
}

SUNSPEC_REGISTERS = ["c_id",
                     "c_did",
                     "c_length",
                     "c_manufacturer",
                     "c_model",
                     "c_version",
                     "c_serialnumber",
                     "c_deviceaddress",
                     "c_sunspec_did",
                     "c_sunspec_length"]

INVERTER_STATUS_REGISTERS = ["status",
                             "vendor_status",
                             "rrcr_state",
                             "active_power_limit",
                             "cosphi",
                             "commit_power_control_settings",
                             "restore_power_control_default_settings",
                             "reactive_power_config",
                             "reactive_power_response_time",
                             "advanced_power_control_enable",
                             "export_control_mode",
                             "export_control_limit_mode",
                             "export_control_site_limit",
                             "storage_control_mode",
                             "storage_ac_charge_policy",
                             "storage_ac_charge_limit",
                             "storage_backup_reserved_setting",
                             "storage_default_mode",
                             "rc_cmd_timeout",
                             "rc_cmd_mode",
                             "rc_charge_limit",
                             "rc_discharge_limit"]

INVERTER_POLL_REGISTERS = ["current",                        # 40071 - A  - AC Total Current
                           "l1_current",                     # 40072 - A  - AC Line 1 Current
                           "l2_current",                     # 40073 - A  - AC Line 2 Current
                           "l3_current",                     # 40074 - A  - AC Line 3 Current
                           "l1n_voltage",                    # 40080 - A  - AC Line 1 to Neutral Voltage
                           "l2n_voltage",                    # 40081 - A  - AC Line 2 to Neutral Voltage
                           "l3n_voltage",                    # 40082 - A  - AC Line 3 to Neutral Voltage
                           "power_ac",                       # 40084 - A  - AC Active Power
                           "frequency",                      # 40071 - Hz - AC Frequency
                           "energy_total",                   # 40071 - Wh - AC Lifetime Energy production
                           "current_dc",                     # 40071 - A  - DC Current
                           "voltage_dc",                     # 40071 - V  - DC Voltage
                           "temperature",                    # 40104 - C  - Heat Sink Temperature

                           "current_scale",                  # 40076 - Scale factor for Current values
                           "energy_total_scale",             # 40079 - Scale factor for Energy values
                           "voltage_scale",                  # 40083 - Scale factor for Voltage values
                           "power_ac_scale",                 # 40085 - Scale factor for AC Power values
                           "power_dc_scale",                 # 40102 - Scale factor for DC Power values
                           "temperature_scale",              # 40105 - Scale factor for Temperature values

                           "status",                         # 40108 - Inverter Status
                           "vendor_status",                  # 40109 - Vendor Specific Status Code and error codes

                           "active_power_limit",             # 61441 - F001 - Percent of maximum power (1-100)
                           "commit_power_control_settings",  # 61696 - F100 - Commit Power Control Settings
                           "restore_power_control_default_settings",  # 61761 - F101 - Restore Power Control Default Settings
                           ]


class SolarEdgeInverter(solaredge_modbus.Inverter):
    def __init__(self, device="/dev/ttyUSB0", baud=9600, timeout=2):
        """
        Initializes the SolarEdgeInverter class with default values.
        :param device: The device path for the inverter connection (default: "/dev/ttyUSB0").
        :param baud: The baud rate for the inverter connection (default: 9600).
        """

        # Setup logging
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info("Initializing SolarEdgeInverter class...")

        # Store device and baud rate
        self.device = device
        self.baud = baud
        self.timeout = timeout

        # Initialize all values from the example data (except scale factors)
        self.c_id: str = None
        self.c_did: str = None
        self.c_length: str = None
        self.c_manufacturer: str = None
        self.c_model: str = None
        self.c_version: str = None
        self.c_serialnumber: str = None
        self.c_deviceaddress: str = None
        self.c_sunspec_did: str = None
        self.c_sunspec_length: str = None

        self.current: float = None
        self.l1_current: float = None
        self.l2_current: float = None
        self.l3_current: float = None
        self.l1_voltage: float = None
        self.l2_voltage: float = None
        self.l3_voltage: float = None
        self.l1n_voltage: float = None
        self.l2n_voltage: float = None
        self.l3n_voltage: float = None

        self.power_ac: float = None
        self.frequency: float = None
        self.power_apparent: float = None
        self.power_reactive: float = None
        self.power_factor: float = None
        self.energy_total: float = None
        self.current_dc: float = None
        self.voltage_dc: float = None
        self.power_dc: float = None
        self.temperature: float = None
        self.status: int = None
        self.vendor_status: int = None
        self.rrcr_state: int = None
        self.active_power_limit: int = None
        self.cosphi: float = None

        self.commit_power_control_settings: int = None
        self.restore_power_control_default_settings: int = None
        self.reactive_power_config: int = None
        self.reactive_power_response_time: int = None
        self.advanced_power_control_enable: int = None
        self.export_control_mode: int = None
        self.export_control_limit_mode: int = None
        self.export_control_site_limit: float = None

        # Read inverter data
        self._read_inverter_all()

    def _read_inverter_all(self):
        """
        Connects to the inverter, reads all registers, applies scaling factors,
        and stores the scaled data in the class attributes.
        """
        # Initialize the connection
        super().__init__(device=self.device, baud=self.baud, timeout=self.timeout)
        self.connect()

        if not self.connected():
            logger.error("Failed to connect to the inverter.")
            raise ConnectionError("Failed to connect to the inverter.")

        # Read all registers
        logger.info("Reading all registers from the inverter...")
        registers = self.read_all()

        # Set SunSpec registers
        logger.debug("Read SunSpec registers...")
        for key in SUNSPEC_REGISTERS:
            if key in registers:
                if hasattr(self, key):
                    setattr(self, key, registers[key])
                    logger.debug(f"\t{key:<40s} - {registers[key]}")
                else:
                    logger.warning(f"Warning: Attribute {key} not found in class.")

        # Apply scaling factors and store the scaled data
        logger.debug("Read scaling factors and setting registers...")
        for key, scale_key in REGISTER_SCALE_FACTORS.items():
            if key in registers and scale_key in registers:
                scaled_value = round(float(registers[key]) * (10 ** int(registers[scale_key])), int(registers[scale_key]))

            # Store the scaled value in the corresponding attribute
            if hasattr(self, key):
                setattr(self, key, scaled_value)
                logger.debug(f"\t{key:<40s} - {registers[key]}")
            else:
                logger.warning(f"Warning: Attribute {key} not found in class.")

        # Set Inverter Status registers
        logger.debug("Read Inverter Status registers...")
        for key in INVERTER_STATUS_REGISTERS:
            if key in registers:
                if hasattr(self, key):
                    key_type_conversion = self.registers[key][4]
                    setattr(self, key, key_type_conversion(registers[key]))
                    logger.debug(f"\t{key:<40s} - {registers[key]}")

                else:
                    logger.warning(f"Warning: Attribute {key} not found in class.")

        # Disconnect after reading
        self.disconnect()

    def read_inverter_poll_registers(self):
        
        """
        Connects to the inverter, reads the poll registers, applies scaling factors,
        and stores the scaled data in the class attributes.
        """
        # Read poll registers
        logger.info("Reading inverter poll registers from the inverter...")

        # Initialize the connection
        self.connect()

        if not self.connected():
            logger.error("Failed to connect to the inverter.")
            raise ConnectionError("Failed to connect to the inverter.")

        read_registers = {}
        for register in INVERTER_POLL_REGISTERS:
            try:
                read_registers.update(self.read(register))
            except Exception as e:
                logger.error(f"Error reading register {register}: {e}")
                read_registers[register] = None
        
        print(read_registers)

        # Apply scaling factors and store the scaled data
        logger.debug("Read scaling factors and setting registers...")
        for key, scale_key in REGISTER_SCALE_FACTORS.items():
            if key in read_registers and scale_key in read_registers:
                scaled_value = round(float(read_registers[key]) * (10 ** int(read_registers[scale_key])), int(read_registers[scale_key]))

            # Store the scaled value in the corresponding attribute
            if hasattr(self, key):
                setattr(self, key, scaled_value)
                logger.debug(f"\t{key:<40s} - {scaled_value}")
            else:
                logger.warning(f"Warning: Attribute {key} not found in class.")

        # Disconnect after reading
        self.disconnect()
    
    def get_inverter_registers_as_json(self):
        """
        Returns the current status of registers as a JSON-like dictionary.
        """
        logger.info("Get inverter registers as json")

        # self.read_inverter_poll_registers()
        
        all_data = {}
        for attribute in dir(self):
            if attribute in SUNSPEC_REGISTERS + INVERTER_POLL_REGISTERS and not callable(getattr(self, attribute)):
                value = getattr(self, attribute)
                all_data[attribute] = value
                
        return all_data
    
    def get_inverter_poll_registers_as_json(self):
        """
        Returns the current status of all poll registers as a JSON-like dictionary.
        """
        logger.info("Get inverter poll registers as json")

        #self.read_inverter_poll_registers()
        
        poll_data = {}
        for attribute in dir(self):
            if attribute in INVERTER_POLL_REGISTERS and not callable(getattr(self, attribute)):
                value = getattr(self, attribute)
                poll_data[attribute] = value
                
        return poll_data

    def print_inverter_data(self):
        """
        Prints all the inverter data stored in the class attributes.
        """

        print("\nInverter Data: \n\tAttribute           : Value")
        for attribute in dir(self):
            if attribute.startswith("c_") and not callable(getattr(self, attribute)):
                value = getattr(self, attribute)
                print(f"\t{attribute:<20}: {value}")
        print("\n")

    def print_all(self):
        """
        Prints the current status of all registers.
        """
        print("\nInverter Registers and settings: \n\tRegister and settings                   : Value")
        for attribute in dir(self):
            if not attribute.startswith("_") and not callable(getattr(self, attribute)) and not attribute in ["registers", "battery_dids", "client", "meter_dids", "logger"]:
                value = getattr(self, attribute)
                print(f"\t{attribute:<40}: {value}")
        print("\n")

    def set_production_limit(self, limit: int):
        """
        Sets the production limit of the inverter. These settings are volatile and will be lost on power cycle.

        61696 - F100 - "commit_power_control_settings" - Commit Power Control Settings
                         Write:
                           1 = Commit
                         Read:
                           0 = Restore defaults successfully
                           0xFFFF (65535) = Error
        61761 - F101 - "restore_power_control_default_settings" - Restore Power Control Default Settings
                         Write:
                           1 = Commit
        61441 - F001 - "active_power_limit" - Percent of maximum power (1-100)

        Set percent of maximum power (1-100) and commit the setting.

        :param limit - The production limit to set (0-100) percent.
        """

        if not (0 <= limit <= 100):
            logger.error(f"Limit must be between 0 and 100. Got: {limit}")
            raise ValueError("Limit must be between 0 and 100.")

        # Initialize the connection
        self.connect()

        if not self.connected():
            logger.error("Failed to connect to the inverter.")
            raise ConnectionError("Failed to connect to the inverter.")

        # Set active power limit
        logger.info(f"Setting active power limit to {limit}%")
        self.write("active_power_limit", limit)

        # Apply the setting
        # logger.info("Committing power control settings...")
        # self.write("commit_power_control_settings", 1)

        # Disconnect after setting
        self.disconnect()

    def set_restore_power_control_defaults(self):
        """
        Restores the power control settings to their default values.

        61761 - F101 - "restore_power_control_default_settings" - Restore Power Control Default Settings
                        Write:
                        1 = Commit
        """

        # Initialize the connection
        self.connect()

        if not self.connected():
            logger.error("Failed to connect to the inverter.")
            raise ConnectionError("Failed to connect to the inverter.")

        # Restore defaults
        logger.info("Restoring power control default settings...")
        self.write("restore_power_control_default_settings", 1)


       # Set active power limit
        logger.info("Revert setting active power limit to 100%")
        self.write("active_power_limit", 100)
        
        # Apply the setting
        # logger.info("Committing power control settings...")
        # self.write("commit_power_control_settings", 1)
        
        # Disconnect after setting
        self.disconnect()
