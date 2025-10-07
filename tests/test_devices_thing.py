"""Test LaMarzoccoThing class."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from pylamarzocco.devices._thing import LaMarzoccoThing, cloud_only, models_supported
from pylamarzocco.clients import LaMarzoccoBluetoothClient, LaMarzoccoCloudClient
from pylamarzocco.const import ModelCode
from pylamarzocco.exceptions import CloudOnlyFunctionality, UnsupportedModel
from pylamarzocco.models import (
    ThingDashboardConfig, 
    ThingSettings, 
    ThingStatistics, 
    WebSocketDetails
)


class TestLaMarzoccoThing:
    """Test LaMarzoccoThing class."""

    def test_init_with_no_clients(self) -> None:
        """Test initialization without any clients."""
        serial = "test-serial-123"
        thing = LaMarzoccoThing(serial)
        
        assert thing.serial_number == serial
        assert thing._cloud_client is None
        assert thing._bluetooth_client is None
        assert thing._update_callback is None
        assert isinstance(thing.dashboard, ThingDashboardConfig)
        assert isinstance(thing.settings, ThingSettings)
        assert isinstance(thing.statistics, ThingStatistics)
        assert thing.dashboard.serial_number == serial
        assert thing.settings.serial_number == serial
        assert thing.statistics.serial_number == serial

    def test_init_with_cloud_client(self) -> None:
        """Test initialization with cloud client."""
        serial = "test-serial-456"
        cloud_client = MagicMock(spec=LaMarzoccoCloudClient)
        
        thing = LaMarzoccoThing(serial, cloud_client=cloud_client)
        
        assert thing.serial_number == serial
        assert thing._cloud_client == cloud_client
        assert thing._bluetooth_client is None

    def test_init_with_bluetooth_client(self) -> None:
        """Test initialization with bluetooth client."""
        serial = "test-serial-789"
        bluetooth_client = MagicMock(spec=LaMarzoccoBluetoothClient)
        
        thing = LaMarzoccoThing(serial, bluetooth_client=bluetooth_client)
        
        assert thing.serial_number == serial
        assert thing._cloud_client is None
        assert thing._bluetooth_client == bluetooth_client

    def test_init_with_both_clients(self) -> None:
        """Test initialization with both clients."""
        serial = "test-serial-both"
        cloud_client = MagicMock(spec=LaMarzoccoCloudClient)
        bluetooth_client = MagicMock(spec=LaMarzoccoBluetoothClient)
        
        thing = LaMarzoccoThing(serial, cloud_client=cloud_client, bluetooth_client=bluetooth_client)
        
        assert thing.serial_number == serial
        assert thing._cloud_client == cloud_client
        assert thing._bluetooth_client == bluetooth_client

    def test_websocket_with_cloud_client(self) -> None:
        """Test websocket property with cloud client."""
        serial = "test-websocket"
        cloud_client = MagicMock(spec=LaMarzoccoCloudClient)
        websocket_details = WebSocketDetails()
        cloud_client.websocket = websocket_details
        
        thing = LaMarzoccoThing(serial, cloud_client=cloud_client)
        
        assert thing.websocket == websocket_details

    def test_websocket_without_cloud_client(self) -> None:
        """Test websocket property without cloud client."""
        serial = "test-no-websocket"
        thing = LaMarzoccoThing(serial)
        
        websocket = thing.websocket
        assert isinstance(websocket, WebSocketDetails)
        assert websocket.connected is False


class TestCloudOnlyDecorator:
    """Test cloud_only decorator functionality."""

    def test_cloud_only_with_client(self) -> None:
        """Test cloud_only decorator when cloud client is available."""
        
        class TestThing(LaMarzoccoThing):
            @cloud_only
            async def test_method(self, value: int) -> int:
                return value * 2
        
        cloud_client = MagicMock(spec=LaMarzoccoCloudClient)
        thing = TestThing("test", cloud_client=cloud_client)
        
        # Should not raise exception when cloud client is available
        async def run_test():
            result = await thing.test_method(5)
            assert result == 10
        
        # Run the async test
        import asyncio
        asyncio.run(run_test())

    def test_cloud_only_without_client(self) -> None:
        """Test cloud_only decorator when cloud client is not available."""
        
        class TestThing(LaMarzoccoThing):
            @cloud_only
            async def test_method(self, value: int) -> int:
                return value * 2
        
        thing = TestThing("test")  # No cloud client
        
        async def run_test():
            with pytest.raises(CloudOnlyFunctionality):
                await thing.test_method(5)
        
        import asyncio
        asyncio.run(run_test())


class TestModelsSupportedDecorator:
    """Test models_supported decorator functionality."""

    def test_models_supported_with_supported_model(self) -> None:
        """Test models_supported decorator with supported model."""
        
        class TestThing(LaMarzoccoThing):
            @models_supported((ModelCode.LINEA_MICRA, ModelCode.LINEA_MINI))
            async def test_method(self, value: int) -> int:
                return value * 3
        
        thing = TestThing("test")
        # Set up dashboard with supported model
        thing.dashboard.model_code = ModelCode.LINEA_MICRA
        
        async def run_test():
            result = await thing.test_method(4)
            assert result == 12
        
        import asyncio
        asyncio.run(run_test())

    def test_models_supported_with_unsupported_model(self) -> None:
        """Test models_supported decorator with unsupported model."""
        
        class TestThing(LaMarzoccoThing):
            @models_supported((ModelCode.LINEA_MICRA, ModelCode.LINEA_MINI))
            async def test_method(self, value: int) -> int:
                return value * 3
        
        thing = TestThing("test")
        # Set up dashboard with unsupported model
        thing.dashboard.model_code = ModelCode.GS3_AV
        
        async def run_test():
            with pytest.raises(UnsupportedModel) as exc_info:
                await thing.test_method(4)
            
            error_msg = str(exc_info.value)
            assert "This functionality is only supported on:" in error_msg
            assert "LINEA_MICRA" in error_msg
            assert "LINEA_MINI" in error_msg
        
        import asyncio
        asyncio.run(run_test())

    def test_models_supported_without_dashboard(self) -> None:
        """Test models_supported decorator when dashboard attribute doesn't exist."""
        
        class TestThing:
            @models_supported((ModelCode.LINEA_MICRA,))
            async def test_method(self, value: int) -> int:
                return value * 3
        
        thing = TestThing()
        
        async def run_test():
            with pytest.raises(UnsupportedModel):
                await thing.test_method(4)
        
        import asyncio
        asyncio.run(run_test())

    def test_models_supported_multiple_models(self) -> None:
        """Test models_supported decorator with multiple supported models."""
        
        class TestThing(LaMarzoccoThing):
            @models_supported((ModelCode.LINEA_MICRA, ModelCode.LINEA_MINI, ModelCode.GS3_AV))
            async def test_method(self) -> str:
                return "supported"
        
        thing = TestThing("test")
        
        # Test each supported model
        supported_models = [ModelCode.LINEA_MICRA, ModelCode.LINEA_MINI, ModelCode.GS3_AV]
        
        async def run_test():
            for model in supported_models:
                thing.dashboard.model_code = model
                result = await thing.test_method()
                assert result == "supported"
        
        import asyncio
        asyncio.run(run_test())

    def test_models_supported_error_message_formatting(self) -> None:
        """Test that models_supported generates proper error messages."""
        
        class TestThing(LaMarzoccoThing):
            @models_supported((ModelCode.LINEA_MICRA, ModelCode.LINEA_MINI, ModelCode.GS3_AV))
            async def test_method(self) -> str:
                return "supported"
        
        thing = TestThing("test")
        thing.dashboard.model_code = ModelCode.LINEA_MINI_R  # Unsupported model
        
        async def run_test():
            with pytest.raises(UnsupportedModel) as exc_info:
                await thing.test_method()
            
            error_msg = str(exc_info.value)
            assert "LINEA_MICRA, LINEA_MINI, GS3_AV" in error_msg
        
        import asyncio
        asyncio.run(run_test())