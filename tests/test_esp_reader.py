import unittest
from unittest.mock import AsyncMock, patch, MagicMock
import time
from src.EspReader import EspReader
from aioesphomeapi import SensorInfo, BinarySensorInfo, TextSensorInfo


class TestEspReader(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.reader = EspReader(
            host="192.168.1.100",
            port=6053,
            encryption_key="testkey"
        )

    @patch("src.EspReader.APIClient")
    async def test_connect_and_discover_entities(self, MockClient):
        """ESPHome connection and entity discovery"""

        # Mock client methods
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
        self.assertIn(1, self.reader.meta)
        self.assertIn(2, self.reader.meta)
        self.assertIn(3, self.reader.meta)

        await self.reader.disconnect()
        self.assertFalse(self.reader._connected)

    @patch("src.EspReader.APIClient")
    async def test_get_data_as_json_without_connection_raises(self, MockClient):
        """get_data_as_json raises RuntimeError if not connected"""
        with self.assertRaises(RuntimeError):
            self.reader.get_data_as_json()

    @patch("src.EspReader.APIClient")
    async def test_get_latest_states_returns_empty_dict_initially(self, MockClient):
        """get_latest_states returns empty dict if no states yet"""
        self.assertEqual(self.reader.get_latest_states(), {})

    @patch("src.EspReader.APIClient")
    async def test_ensure_connected_with_mock_reporting(self, MockClient):
        """
        Ensure that ensure_connected waits for all entities that report
        by simulating state updates via _on_state.
        """
        # Mock client methods
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

        # Connect and discover entities
        await self.reader.connect()

        # Simulate all sensors reporting via _on_state
        for key, meta in self.reader.meta.items():
            kind = meta[3]

            class Msg:
                def __init__(self, key, state):
                    self.key = key
                    self.state = state

            if kind == "sensor":
                self.reader._on_state(Msg(key, 42))
            elif kind == "binary_sensor":
                self.reader._on_state(Msg(key, 1))  # True
            elif kind == "text_sensor":
                self.reader._on_state(Msg(key, "OK"))

        # Call ensure_connected should now find all sensors reported
        await self.reader.ensure_connected(timeout=1.0)

        # All states should now be present
        self.assertEqual(len(self.reader.states), 3)
        for key, state in self.reader.states.items():
            self.assertIn("value", state)
            self.assertIn("last_updated", state)
            self.assertIsInstance(state["last_updated"], float)

        # Assert values according to kind
        self.assertEqual(self.reader.states[1]["value"], 42)       # sensor
        self.assertEqual(self.reader.states[2]["value"], True)     # binary sensor
        self.assertEqual(self.reader.states[3]["value"], "OK")     # text sensor

        await self.reader.disconnect()

    @patch("src.EspReader.APIClient")
    async def test_ensure_connected_timeout_warning(self, MockClient):
        """Test ensure_connected logs a warning if not all sensors report."""
        mock_client = MockClient.return_value
        mock_client.connect = AsyncMock()
        mock_client.disconnect = AsyncMock()
        mock_client.list_entities_services = AsyncMock(
            return_value=(
                [SensorInfo(key=1, object_id="sensor_1", name="Temperature", unit_of_measurement="C")],
                []
            )
        )
        mock_client.subscribe_states = MagicMock()

        await self.reader.connect()

        # Patch logger.warning and asyncio.sleep with AsyncMock
        with patch.object(self.reader.logger, "warning") as mock_warning, patch("asyncio.sleep", new=AsyncMock()):
            await self.reader.ensure_connected(timeout=0.2)
            self.assertTrue(mock_warning.called)
            self.assertIn("Some ESPHome sensors did not report", mock_warning.call_args[0][0])

        await self.reader.disconnect()

    @patch("src.EspReader.APIClient")
    async def test_connect_api_connection_error(self, MockClient):
        """Test connect raises exception on APIConnectionError"""
        mock_client = MockClient.return_value
        mock_client.connect = AsyncMock(side_effect=Exception("API error"))
        with self.assertRaises(Exception):
            await self.reader.connect()

    async def test_disconnect_no_client(self):
        """Test disconnect works if client is None"""
        self.reader.client = None
        await self.reader.disconnect()  # Should not raise

    async def test_on_state_ignores_none_and_nan(self):
        """Test _on_state ignores None and NaN values"""
        self.reader.meta = {1: ("sensor_1", "Temp", "C", "sensor")}

        class Msg:
            def __init__(self, key, state):
                self.key = key
                self.state = state

        self.reader._on_state(Msg(1, None))
        self.assertNotIn(1, self.reader.states)
        self.reader._on_state(Msg(1, float("nan")))
        self.assertNotIn(1, self.reader.states)

    @patch("src.EspReader.EspReader")
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_main_example_loop(self, mock_sleep, MockEspReader):
        """
        Test the example main() loop with 3 iterations.
        Ensures get_data_as_json() is called and output formatting works.
        """
        # Create a mock reader instance
        mock_reader = MockEspReader.return_value

        # Ensure the reader is "connected"
        mock_reader.ensure_connected = AsyncMock()
        mock_reader.get_data_as_json = MagicMock(
            return_value={
                1: {
                    "object_id": "sensor_1",
                    "name": "Temperature",
                    "unit": "C",
                    "value": 25.3,
                    "last_updated": time.time()
                },
                2: {
                    "object_id": "switch_1",
                    "name": "Switch",
                    "unit": "",
                    "value": "ON",
                    "last_updated": time.time()
                },
            }
        )

        # Import the main function locally so we can test it
        from src.EspReader import main

        # Run the main function (3 iterations)
        await main()

        # Assertions: ensure get_data_as_json called multiple times
        self.assertEqual(mock_reader.get_data_as_json.call_count, 3)
        # Ensure sleep was awaited 3 times
        self.assertEqual(mock_sleep.await_count, 3)
        # Ensure ensure_connected was called once
        mock_reader.ensure_connected.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
