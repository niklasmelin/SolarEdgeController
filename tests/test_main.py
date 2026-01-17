import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from solar_controller.main import main


@pytest.fixture
def mock_inverter():
    inv = MagicMock()
    # Async methods
    inv.check_connection = AsyncMock(return_value=True)
    inv.read_all_registers = AsyncMock(return_value=None)
    inv.update_poll_registers = AsyncMock(return_value=None)
    inv.update_control_registers = AsyncMock(return_value=None)
    inv.update_status_registers = AsyncMock(return_value=None)
    # Sync methods
    inv.get_registers_as_json.return_value = {"power_ac": 1234.0}
    inv.get_ha_sensors = MagicMock(return_value={})
    inv.get_control_data = MagicMock(return_value={})
    # Optional: scale factor method
    inv.set_max_power_scale_factor = AsyncMock()
    return inv


@pytest.fixture
def mock_reader():
    reader = MagicMock()
    # Async methods
    reader.ensure_connected = AsyncMock(side_effect=lambda: setattr(reader, "_connected", True))
    reader.disconnect = AsyncMock()
    # Sync methods
    reader.get_control_data.return_value = {
        "grid_import_power": (100.0, 1234567890.0),
        "grid_export_power": (50.0, 1234567890.0),
        "last_updated": 1234567890.0,
    }
    reader.get_sensor_data_as_json.return_value = {
        "sensor_1": {"object_id": "sensor_1", "name": "Grid Import", "value": 100, "unit": "W"},
        "sensor_2": {"object_id": "sensor_2", "name": "Grid Export", "value": 50, "unit": "W"},
    }
    return reader


@pytest.mark.asyncio
async def test_main_loop_runs(mock_inverter, mock_reader):
    # Create a stop event to break the infinite loop
    stop_event = asyncio.Event()

    # Schedule the stop_event to be set almost immediately
    asyncio.get_running_loop().call_later(0.01, stop_event.set)

    # Patch the factory functions where they are looked up in main.py
    with patch("solar_controller.main.create_inverter", return_value=mock_inverter), \
         patch("solar_controller.main.create_sensor", return_value=mock_reader), \
         patch("solar_controller.config.load_config", return_value=mock_inverter.config):  # adjust to your config mock

        # Run the main function with stop_event injected
        await main(stop_event=stop_event)

        # Assert the ESPHome reader connection was checked
        mock_reader.ensure_connected.assert_awaited()

        # Assert the inverter connection was checked
        mock_inverter.check_connection.assert_awaited()

        # Assert inverter registers were read at least once
        mock_inverter.read_all_registers.assert_awaited()

        # Assert control data was retrieved
        mock_reader.get_control_data.assert_called()

        # Assert registers were retrieved as JSON
        mock_inverter.get_registers_as_json.assert_called()

@pytest.mark.asyncio
async def test_main_loop_handles_low_pv(mock_inverter, mock_reader):
    """
    Test that the main loop handles very low solar production correctly
    by returning 100% scale factor (no regulation).
    """
    from solar_controller.controller.solar_regulator import SolarRegulator

    # Patch factories
    with patch("solar_controller.main.create_inverter", return_value=mock_inverter), \
         patch("solar_controller.main.create_sensor", return_value=mock_reader), \
         patch("solar_controller.config.load_config", return_value={}):

        regulator = SolarRegulator()
        # Set very low PV to trigger LOW_PV_THRESHOLD
        scale_factor = regulator.new_scale_factor(current_grid_consumption=50, current_solar_production=10)
        assert scale_factor == 100
