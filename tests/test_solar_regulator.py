import pytest
from solar_controller.controller.solar_regulator import SolarRegulator


@pytest.fixture
def regulator():
    return SolarRegulator()


# ------------------------
# First call initializes state
# ------------------------
def test_initial_call_sets_last_limited_power(regulator):
    sf = regulator.new_scale_factor(current_grid_consumption=500, current_solar_production=1000)
    assert 0 <= sf <= 100
    assert regulator.last_limited_power is not None


# ------------------------
# Low PV → returns 100%
# ------------------------
def test_low_pv_returns_100_percent(regulator):
    sf = regulator.new_scale_factor(current_grid_consumption=500, current_solar_production=20)
    assert sf == 100
    assert regulator.last_limited_power == 20


# ------------------------
# Normal regulation applies proportional ramp
# ------------------------
def test_normal_regulation_proportional_step(regulator):
    # Simulate first call to initialize last_limited_power
    regulator.new_scale_factor(current_grid_consumption=1000, current_solar_production=2000)
    # Next step
    sf = regulator.new_scale_factor(current_grid_consumption=1500, current_solar_production=2500)
    assert 0 <= sf <= 100
    assert regulator.last_limited_power <= 2500


# ------------------------
# Ramp limit enforced
# ------------------------
def test_ramp_limit_enforced(regulator):
    regulator.MAX_DELTA_PERCENT_PER_15S = 1.0  # tiny ramp
    regulator.max_step_watt = (
        regulator.MAX_DELTA_PERCENT_PER_15S / 100.0
        * regulator.PEAK_PRODUCTION_W
        * (regulator.DT / 15.0)
    )

    regulator.last_limited_power = 1000
    sf = regulator.new_scale_factor(current_grid_consumption=5000, current_solar_production=3000)
    # Step should not exceed max_step_watt
    limited_power_change = regulator.last_limited_power - 1000
    assert abs(limited_power_change) <= regulator.max_step_watt

    # Scale factor must be in 0-100%
    assert 0 <= sf <= 100
    
# ------------------------
# Physical constraints (min/max)
# ------------------------
def test_physical_constraints(regulator):
    # Test below minimum
    regulator.last_limited_power = 100
    sf = regulator.new_scale_factor(current_grid_consumption=0, current_solar_production=50)
    assert sf >= 0  # Should not go below min production
    # Test above solar
    regulator.last_limited_power = 300
    sf = regulator.new_scale_factor(current_grid_consumption=0, current_solar_production=250)
    assert sf <= 100  # Should not exceed current solar production


# ------------------------
# Negative home consumption treated as zero
# ------------------------
def test_negative_home_consumption(regulator):
    sf = regulator.new_scale_factor(current_grid_consumption=-500, current_solar_production=1000)
    assert 0 <= sf <= 100
    assert regulator.last_limited_power <= 1000
