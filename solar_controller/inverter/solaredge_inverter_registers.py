from enum import Enum
from typing import Dict, Any

class PollGroup(Enum):
    IDENTITY = "identity"
    POLL = "poll"
    CONTROL = "control"
    STATUS = "status"

# -------------------------------
# All registers
# -------------------------------
REGISTERS: Dict[str, Dict[str, Any]] = {
    # SunSpec identity
    "c_id": {"scale": None, "group": PollGroup.IDENTITY},
    "c_did": {"scale": None, "group": PollGroup.IDENTITY},
    "c_length": {"scale": None, "group": PollGroup.IDENTITY},
    "c_manufacturer": {"scale": None, "group": PollGroup.IDENTITY},
    "c_model": {"scale": None, "group": PollGroup.IDENTITY},
    "c_version": {"scale": None, "group": PollGroup.IDENTITY},
    "c_serialnumber": {"scale": None, "group": PollGroup.IDENTITY},
    "c_deviceaddress": {"scale": None, "group": PollGroup.IDENTITY},
    "c_sunspec_did": {"scale": None, "group": PollGroup.IDENTITY},
    "c_sunspec_length": {"scale": None, "group": PollGroup.IDENTITY},

    # Poll registers (AC/DC measurements)
    "current": {"scale": "current_scale", "group": PollGroup.POLL},
    "l1_current": {"scale": "current_scale", "group": PollGroup.POLL},
    "l2_current": {"scale": "current_scale", "group": PollGroup.POLL},
    "l3_current": {"scale": "current_scale", "group": PollGroup.POLL},

    "l1_voltage": {"scale": "voltage_scale", "group": PollGroup.POLL},
    "l2_voltage": {"scale": "voltage_scale", "group": PollGroup.POLL},
    "l3_voltage": {"scale": "voltage_scale", "group": PollGroup.POLL},

    "l1n_voltage": {"scale": "voltage_scale", "group": PollGroup.POLL},
    "l2n_voltage": {"scale": "voltage_scale", "group": PollGroup.POLL},
    "l3n_voltage": {"scale": "voltage_scale", "group": PollGroup.POLL},

    "power_ac": {"scale": "power_ac_scale", "group": PollGroup.POLL},
    "power_apparent": {"scale": "power_apparent_scale", "group": PollGroup.POLL},
    "power_reactive": {"scale": "power_reactive_scale", "group": PollGroup.POLL},
    "power_factor": {"scale": "power_factor_scale", "group": PollGroup.POLL},

    "frequency": {"scale": "frequency_scale", "group": PollGroup.POLL},
    "energy_total": {"scale": "energy_total_scale", "group": PollGroup.POLL},

    "current_dc": {"scale": "current_dc_scale", "group": PollGroup.POLL},
    "voltage_dc": {"scale": "voltage_dc_scale", "group": PollGroup.POLL},
    "power_dc": {"scale": "power_dc_scale", "group": PollGroup.POLL},

    "temperature": {"scale": "temperature_scale", "group": PollGroup.POLL},

    # Status registers
    "status": {"scale": None, "group": PollGroup.STATUS},
    "vendor_status": {"scale": None, "group": PollGroup.STATUS},
    "rrcr_state": {"scale": None, "group": PollGroup.STATUS},
    "active_power_limit": {"scale": None, "group": PollGroup.STATUS},
    "cosphi": {"scale": None, "group": PollGroup.STATUS},
    "commit_power_control_settings": {"scale": None, "group": PollGroup.STATUS},
    "restore_power_control_default_settings": {"scale": None, "group": PollGroup.STATUS},
    "reactive_power_config": {"scale": None, "group": PollGroup.STATUS},
    "reactive_power_response_time": {"scale": None, "group": PollGroup.STATUS},
    "advanced_power_control_enable": {"scale": None, "group": PollGroup.STATUS},
    "export_control_mode": {"scale": None, "group": PollGroup.STATUS},
    "export_control_limit_mode": {"scale": None, "group": PollGroup.STATUS},
    "export_control_site_limit": {"scale": None, "group": PollGroup.STATUS},
    "storage_control_mode": {"scale": None, "group": PollGroup.STATUS},
    "storage_ac_charge_policy": {"scale": None, "group": PollGroup.STATUS},
    "storage_ac_charge_limit": {"scale": None, "group": PollGroup.STATUS},
    "storage_backup_reserved_setting": {"scale": None, "group": PollGroup.STATUS},
    "storage_default_mode": {"scale": None, "group": PollGroup.STATUS},
    "rc_cmd_timeout": {"scale": None, "group": PollGroup.STATUS},
    "rc_cmd_mode": {"scale": None, "group": PollGroup.STATUS},
    "rc_charge_limit": {"scale": None, "group": PollGroup.STATUS},
    "rc_discharge_limit": {"scale": None, "group": PollGroup.STATUS},

    # Scaling factors
    "current_scale": {"scale": None, "group": PollGroup.POLL},
    "voltage_scale": {"scale": None, "group": PollGroup.POLL},
    "power_ac_scale": {"scale": None, "group": PollGroup.POLL},
    "power_dc_scale": {"scale": None, "group": PollGroup.POLL},
    "energy_total_scale": {"scale": None, "group": PollGroup.POLL},
    "temperature_scale": {"scale": None, "group": PollGroup.POLL},
    "frequency_scale": {"scale": None, "group": PollGroup.POLL},
    "power_apparent_scale": {"scale": None, "group": PollGroup.POLL},
    "power_reactive_scale": {"scale": None, "group": PollGroup.POLL},
    "power_factor_scale": {"scale": None, "group": PollGroup.POLL},
    "current_dc_scale": {"scale": None, "group": PollGroup.POLL},
}
