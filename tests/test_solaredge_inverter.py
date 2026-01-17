import pytest
from unittest.mock import AsyncMock, MagicMock
from solar_controller.inverter.solaredge_inverter import SolarEdgeInverter
from solar_controller.inverter.solaredge_inverter_registers import REGISTERS, PollGroup


@pytest.fixture
def inverter():
    inv = SolarEdgeInverter(device="/dev/null")
    inv.logger = MagicMock()
    # Initialize all registers to None
    for reg in REGISTERS.keys():
        setattr(inv, reg, None)
    return inv


# ------------------------
# get_control_data
# ------------------------
def test_get_control_data(inverter):
    inverter.power_ac = 123.45
    inverter.active_power_limit = 80
    inverter.last_updated = 9999
    data = inverter.get_control_data()
    assert data["solar_production"] == 123.45
    assert data["power_limit"] == 80
    assert data["last_updated"] == 9999


# ------------------------
# _apply_registers scaling
# ------------------------
def test_apply_registers_scaling(inverter):
    raw = {}
    for k, reg in REGISTERS.items():
        raw[k] = 1.0
        if reg.scale:
            raw[reg.scale] = 0
    inverter._apply_registers(raw, list(REGISTERS.keys()))
    for k in REGISTERS.keys():
        assert getattr(inverter, k) is not None


def test_apply_registers_invalid_scale_logs_warning(inverter):
    # Find a register with a scale
    scale_reg_name = next((k for k, v in REGISTERS.items() if v.scale), None)
    if not scale_reg_name:
        pytest.skip("No register with a scale found")

    # Find a main register using this scale
    main_reg_name = next((k for k, v in REGISTERS.items() if v.scale == scale_reg_name), None)
    if not main_reg_name:
        pytest.skip("No register references the scale")

    raw = {main_reg_name: 1.0, scale_reg_name: "invalid"}  # invalid scale

    inverter.logger.warning = MagicMock()
    inverter._apply_registers(raw, [main_reg_name])
    inverter.logger.warning.assert_called()


def test_apply_registers_missing_scale(inverter):
    main_reg_name = next((k for k, v in REGISTERS.items() if v.scale), None)
    if not main_reg_name:
        pytest.skip("No register with scale")
    raw = {main_reg_name: 2.0}  # no scale provided
    inverter._apply_registers(raw, [main_reg_name])
    assert getattr(inverter, main_reg_name) == 2.0


# ------------------------
# get_ha_sensors
# ------------------------
def test_get_ha_sensors_returns_correct_keys(inverter):
    # Prepare dummy values only for registers that are valid HA sensors
    for name, reg in REGISTERS.items():
        if reg.ha and not name.endswith("_scale"):
            # Assign value
            setattr(inverter, name, 100.0)
            # Assign scale if relevant
            if reg.scale:
                setattr(inverter, reg.scale, 0)

    sensors = inverter.get_ha_sensors()
    print(sensors)

    for name, reg in REGISTERS.items():
        if not reg.ha or name.endswith("_scale"):
            continue  # skipped by HA function

        # Register should exist in HA sensors
        assert name in sensors, f"{name} should be in HA sensors"
        sensor = sensors[name]

        # Friendly name fallback
        expected_name = getattr(reg.ha, "friendly_name", None)
        if expected_name is None:
            expected_name = name.replace("_", " ").title()

        print(f"Friendly name: {sensor['friendly_name']}, Unique ID: {sensor['unique_id']}, State: {sensor['state']}")
        print(expected_name)
        assert sensor["friendly_name"] == expected_name
        # assert sensor["unique_id"].startswith("123ABC_")
        # Value should equal assigned
        assert sensor["state"] == 100.0
        # Availability should be True
        assert sensor["available"] is True



# ------------------------
# get_registers_as_json
# ------------------------
def test_get_registers_as_json_returns_all(inverter):
    for k in REGISTERS.keys():
        setattr(inverter, k, 42)
    json_data = inverter.get_registers_as_json()
    for k in REGISTERS.keys():
        assert json_data[k] == 42


def test_get_registers_as_json_filtered_by_group(inverter):
    for k in REGISTERS.keys():
        setattr(inverter, k, 42)
    json_data = inverter.get_registers_as_json(group=PollGroup.POLL)
    for k, reg in REGISTERS.items():
        if reg.group == PollGroup.POLL:
            assert k in json_data
        else:
            assert k not in json_data


# ------------------------
# Async update methods
# ------------------------
@pytest.mark.asyncio
async def test_async_update_group_methods(inverter):
    inverter._async_update_group = AsyncMock()

    await inverter.update_poll_registers()
    inverter._async_update_group.assert_awaited_with(PollGroup.POLL)

    await inverter.update_control_registers()
    inverter._async_update_group.assert_awaited_with(PollGroup.CONTROL)

    await inverter.update_status_registers()
    inverter._async_update_group.assert_awaited_with(PollGroup.STATUS)


# ------------------------
# Async power control
# ------------------------
@pytest.mark.asyncio
async def test_set_production_limit_valid(inverter):
    inverter._sync_set_production_limit = MagicMock()
    await inverter.set_production_limit(50)
    inverter._sync_set_production_limit.assert_called_once_with(50)


@pytest.mark.asyncio
async def test_set_production_limit_invalid(inverter):
    with pytest.raises(ValueError):
        await inverter.set_production_limit(-1)
    with pytest.raises(ValueError):
        await inverter.set_production_limit(101)


@pytest.mark.asyncio
async def test_restore_power_control_defaults_calls_sync(inverter):
    inverter._sync_restore_defaults = MagicMock()
    await inverter.restore_power_control_defaults()
    inverter._sync_restore_defaults.assert_called_once()
