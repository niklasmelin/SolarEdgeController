from enum import Enum
from dataclasses import dataclass
from typing import Optional, Dict


class PollGroup(Enum):
    IDENTITY = "identity"
    POLL = "poll"
    CONTROL = "control"
    STATUS = "status"


# -----------------------------------
# Home Assistant metadata
# -----------------------------------
@dataclass(frozen=True)
class HARegisterMeta:
    unit: Optional[str]
    device_class: Optional[str]
    state_class: Optional[str]
    entity_category: Optional[str]
    icon: Optional[str]
    friendly_name: Optional[str] = None
    description: Optional[str] = None


# -----------------------------------
# Register definition
# -----------------------------------
@dataclass(frozen=True)
class RegisterDef:
    scale: Optional[str]
    group: PollGroup
    ha: Optional[HARegisterMeta] = None


# -----------------------------------
# Registers
# -----------------------------------
REGISTERS: Dict[str, RegisterDef] = {
    # -------------------------------
    # SunSpec identity
    # -------------------------------
    "c_id": RegisterDef(None, PollGroup.IDENTITY),
    "c_did": RegisterDef(None, PollGroup.IDENTITY),
    "c_length": RegisterDef(None, PollGroup.IDENTITY),
    "c_manufacturer": RegisterDef(None, PollGroup.IDENTITY),
    "c_model": RegisterDef(None, PollGroup.IDENTITY),
    "c_version": RegisterDef(None, PollGroup.IDENTITY),
    "c_serialnumber": RegisterDef(None, PollGroup.IDENTITY),
    "c_deviceaddress": RegisterDef(None, PollGroup.IDENTITY),
    "c_sunspec_did": RegisterDef(None, PollGroup.IDENTITY),
    "c_sunspec_length": RegisterDef(None, PollGroup.IDENTITY),

    # -------------------------------
    # POLL – AC currents
    # -------------------------------
    "current": RegisterDef(
        "current_scale",
        PollGroup.POLL,
        HARegisterMeta("A", "current", "measurement", None, "mdi:current-ac",
                       "Total Current", "Total AC current output of the inverter"),
    ),
    "l1_current": RegisterDef(
        "current_scale",
        PollGroup.POLL,
        HARegisterMeta("A", "current", "measurement", None, "mdi:current-ac",
                       "L1 Current", "AC current on phase L1"),
    ),
    "l2_current": RegisterDef(
        "current_scale",
        PollGroup.POLL,
        HARegisterMeta("A", "current", "measurement", None, "mdi:current-ac",
                       "L2 Current", "AC current on phase L2"),
    ),
    "l3_current": RegisterDef(
        "current_scale",
        PollGroup.POLL,
        HARegisterMeta("A", "current", "measurement", None, "mdi:current-ac",
                       "L3 Current", "AC current on phase L3"),
    ),

    # -------------------------------
    # POLL – AC voltages
    # -------------------------------
    "l1_voltage": RegisterDef(
        "voltage_scale",
        PollGroup.POLL,
        HARegisterMeta("V", "voltage", "measurement", None, "mdi:sine-wave",
                       "L1-L2 Voltage", "Voltage between phase L1 and L2"),
    ),
    "l2_voltage": RegisterDef(
        "voltage_scale",
        PollGroup.POLL,
        HARegisterMeta("V", "voltage", "measurement", None, "mdi:sine-wave",
                       "L2-L3 Voltage", "Voltage between phase L2 and L3"),
    ),
    "l3_voltage": RegisterDef(
        "voltage_scale",
        PollGroup.POLL,
        HARegisterMeta("V", "voltage", "measurement", None, "mdi:sine-wave",
                       "L3-L1 Voltage", "Voltage between phase L3 and L1"),
    ),
    "l1n_voltage": RegisterDef(
        "voltage_scale",
        PollGroup.POLL,
        HARegisterMeta("V", "voltage", "measurement", None, "mdi:sine-wave",
                       "L1-N Voltage", "Voltage measured from Phase 1 to Neutral"),
    ),
    "l2n_voltage": RegisterDef(
        "voltage_scale",
        PollGroup.POLL,
        HARegisterMeta("V", "voltage", "measurement", None, "mdi:sine-wave",
                       "L2-N Voltage", "Voltage measured from Phase 2 to Neutral"),
    ),
    "l3n_voltage": RegisterDef(
        "voltage_scale",
        PollGroup.POLL,
        HARegisterMeta("V", "voltage", "measurement", None, "mdi:sine-wave",
                       "L3-N Voltage", "Voltage measured from Phase 3 to Neutral"),
    ),

    # -------------------------------
    # POLL – AC power
    # -------------------------------
    "power_ac": RegisterDef(
        "power_ac_scale",
        PollGroup.POLL,
        HARegisterMeta("W", "power", "measurement", None, "mdi:solar-power",
                       "AC Power", "Total AC power output of the inverter"),
    ),
    "power_apparent": RegisterDef(
        "power_apparent_scale",
        PollGroup.POLL,
        HARegisterMeta("VA", "apparent_power", "measurement", None, "mdi:flash",
                       "Apparent Power", "Total AC apparent power (VA)"),
    ),
    "power_reactive": RegisterDef(
        "power_reactive_scale",
        PollGroup.POLL,
        HARegisterMeta("var", "reactive_power", "measurement", None, "mdi:flash-outline",
                       "Reactive Power", "Total reactive power (VAR)"),
    ),
    "power_factor": RegisterDef(
        "power_factor_scale",
        PollGroup.POLL,
        HARegisterMeta(None, "power_factor", "measurement", None, "mdi:cosine-wave",
                       "Power Factor", "Ratio of real power to apparent power"),
    ),

    # -------------------------------
    # POLL – frequency
    # -------------------------------
    "frequency": RegisterDef(
        "frequency_scale",
        PollGroup.POLL,
        HARegisterMeta("Hz", "frequency", "measurement", None, "mdi:sine-wave",
                       "Grid Frequency", "AC grid frequency in Hz"),
    ),

    # -------------------------------
    # POLL – energy (lifetime)
    # -------------------------------
    "energy_total": RegisterDef(
        "energy_total_scale",
        PollGroup.POLL,
        HARegisterMeta("Wh", "energy", "total_increasing", None, "mdi:counter",
                       "Total Energy", "Cumulative energy produced by inverter"),
    ),

    # -------------------------------
    # POLL – DC side
    # -------------------------------
    "current_dc": RegisterDef(
        "current_dc_scale",
        PollGroup.POLL,
        HARegisterMeta("A", "current", "measurement", None, "mdi:current-dc",
                       "DC Current", "DC current from PV array"),
    ),
    "voltage_dc": RegisterDef(
        "voltage_dc_scale",
        PollGroup.POLL,
        HARegisterMeta("V", "voltage", "measurement", None, "mdi:current-dc",
                       "DC Voltage", "DC voltage from PV array"),
    ),
    "power_dc": RegisterDef(
        "power_dc_scale",
        PollGroup.POLL,
        HARegisterMeta("W", "power", "measurement", None, "mdi:solar-power-variant",
                       "DC Power", "DC power from PV array"),
    ),

    # -------------------------------
    # POLL – temperature
    # -------------------------------
    "temperature": RegisterDef(
        "temperature_scale",
        PollGroup.POLL,
        HARegisterMeta("°C", "temperature", "measurement", None, "mdi:thermometer",
                       "Inverter Temperature", "Internal temperature of inverter"),
    ),

    # -------------------------------
    # Scaling registers (internal only)
    # -------------------------------
    "current_scale": RegisterDef(None, PollGroup.POLL),
    "voltage_scale": RegisterDef(None, PollGroup.POLL),
    "power_ac_scale": RegisterDef(None, PollGroup.POLL),
    "power_dc_scale": RegisterDef(None, PollGroup.POLL),
    "energy_total_scale": RegisterDef(None, PollGroup.POLL),
    "temperature_scale": RegisterDef(None, PollGroup.POLL),
    "frequency_scale": RegisterDef(None, PollGroup.POLL),
    "power_apparent_scale": RegisterDef(None, PollGroup.POLL),
    "power_reactive_scale": RegisterDef(None, PollGroup.POLL),
    "power_factor_scale": RegisterDef(None, PollGroup.POLL),
    "current_dc_scale": RegisterDef(None, PollGroup.POLL),
}
