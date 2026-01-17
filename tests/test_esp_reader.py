import unittest
from unittest.mock import AsyncMock, patch, MagicMock
import time
from solar_controller.sensors.esphome_reader import ESPHomeReader
from aioesphomeapi import SensorInfo, BinarySensorInfo, TextSensorInfo


class TestESPHomeReader(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.reader = ESPHomeReader(
            host="192.168.1.100",
            port=6053,
            encryption_key="testkey"
        )

    @patch("solar_controller.sensors.esphome_reader.APIClient")
    async def test_connect_and_discover_entities(self, MockClient):
        """ESPHome connection and entity discovery"""
        mock_client = MockClient.return_value
        mock_client.connect = AsyncMock()
        mock_client.disconnect = AsyncMock()
        mock_client.list_entities_services = AsyncMock(
            return_value=(
                [
                    SensorInfo(key=1, object_id="sensor_1", name="Temperature", unit_of_measurement="C"),
                    BinarySensorInfo(key=2, object_id="switch_1", name="Switch"),
                    TextSensorInfo(key=3, object_id="text_1", name="Status"),
                ],
                []
            )
        )
        mock_client.subscribe_states = MagicMock()

        await self.reader.connect()
        self.assertTrue(self.reader._connected)
        self.assertEqual(len(self.reader.meta), 3)

        await self.reader.disconnect()
        self.assertFalse(self.reader._connected)

    async def test_get_control_data_returns_standardized_keys(self):
        """get_control_data returns decoupled standardized keys"""
        # Simulate connected state
        self.reader._connected = True
        now = time.time()
        self.reader.states = {
            1: {"value": 5.2, "last_updated": now},
            2: {"value": 3.1, "last_updated": now}
        }
        self.reader.meta = {
            1: ("momentary_active_import", "Import", "W", "sensor"),
            2: ("momentary_active_export", "Export", "W", "sensor")
        }

        result = self.reader.get_control_data()
        self.assertIn("grid_import_power", result)
        self.assertIn("grid_export_power", result)

        # Validate value and timestamp, including scaling from kW to W
        val, ts = result["grid_import_power"]
        self.assertEqual(val, 5200)
        self.assertEqual(ts, now)

        val, ts = result["grid_export_power"]
        self.assertEqual(val, 3100)
        self.assertEqual(ts, now)

    async def test_get_control_data_returns_default_for_missing_values(self):
        """Missing sensors return '<no value>' and None timestamp"""
        self.reader._connected = True
        self.reader.states = {}
        self.reader.meta = {
            1: ("momentary_active_import", "Import", "W", "sensor"),
            2: ("momentary_active_export", "Export", "W", "sensor")
        }

        result = self.reader.get_control_data()
        self.assertEqual(result["grid_import_power"], ["<no value>", None])
        self.assertEqual(result["grid_export_power"], ["<no value>", None])

    @patch("solar_controller.sensors.esphome_reader.APIClient")
    async def test_get_latest_states_returns_empty_dict_initially(self, MockClient):
        """get_latest_states returns empty dict if no states yet"""
        self.assertEqual(self.reader.get_latest_states(), {})

    async def test_on_state_ignores_none_and_nan(self):
        """_on_state ignores None and NaN values"""
        self.reader.meta = {1: ("sensor_1", "Temp", "C", "sensor")}

        class Msg:
            def __init__(self, key, state):
                self.key = key
                self.state = state

        self.reader._on_state(Msg(1, None))
        self.assertNotIn(1, self.reader.states)
        self.reader._on_state(Msg(1, float("nan")))
        self.assertNotIn(1, self.reader.states)

    async def test_disconnect_no_client(self):
        """Test disconnect works if client is None"""
        self.reader.client = None
        await self.reader.disconnect()  # Should not raise

    async def test_on_state_binary_and_text_values(self):
        """_on_state handles binary 0/1 and text empty correctly"""
        self.reader.meta = {
            1: ("binary_1", "Switch", "", "binary_sensor"),
            2: ("text_1", "Status", "", "text_sensor")
        }

        class Msg:
            def __init__(self, key, state):
                self.key = key
                self.state = state

        # binary 0 → False
        self.reader._on_state(Msg(1, 0))
        self.assertEqual(self.reader.states[1]["value"], False)

        # text empty string → ""
        self.reader._on_state(Msg(2, ""))
        self.assertEqual(self.reader.states[2]["value"], "")

    async def test_ensure_connected_timeout_and_logging(self):
        """ensure_connected logs warning if sensors do not report"""
        self.reader._connected = True
        self.reader.meta = {1: ("sensor_1", "Test", "W", "sensor")}
        self.reader.states = {}  # no reporting

        with patch.object(self.reader.logger, "warning") as mock_warn, patch("asyncio.sleep", new=AsyncMock()):
            await self.reader.ensure_connected(timeout=0.1)
            self.assertTrue(mock_warn.called)
            self.assertIn("Some ESPHome sensors did not report", mock_warn.call_args[0][0])

    @patch("solar_controller.sensors.esphome_reader.APIClient")
    async def test_get_data_as_json_returns_all_sensors(self, MockClient):
        mock_client = MockClient.return_value
        mock_client.connect = AsyncMock()
        mock_client.disconnect = AsyncMock()
        mock_client.list_entities_services = AsyncMock(
            return_value=(
                [
                    SensorInfo(key=1, object_id="sensor_1", name="Temperature", unit_of_measurement="C"),
                    BinarySensorInfo(key=2, object_id="switch_1", name="Switch"),
                    TextSensorInfo(key=3, object_id="text_1", name="Status"),
                ],
                []
            )
        )
        mock_client.subscribe_states = MagicMock()

        await self.reader.connect()

        # Fake states
        now = time.time()
        self.reader.states = {
            1: {"value": 25.0, "last_updated": now},
            2: {"value": True, "last_updated": now},
            3: {"value": "OK", "last_updated": now},
        }

        data = self.reader.get_sensor_data_as_json()

        # Assert all keys exist
        self.assertIn(1, data)
        self.assertIn(2, data)
        self.assertIn(3, data)
        self.assertEqual(data[1]["value"], 25.0)
        self.assertEqual(data[2]["value"], "ON")
        self.assertEqual(data[3]["value"], "OK")


if __name__ == "__main__":
    unittest.main()
