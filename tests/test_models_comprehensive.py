"""Comprehensive tests for model classes."""

from unittest.mock import AsyncMock, MagicMock
import pytest

from pylamarzocco.models import WebSocketDetails
from pylamarzocco.models._statistics import CoffeeAndFlushCounter
from pylamarzocco.const import WidgetType


class TestWebSocketDetails:
    """Test WebSocketDetails model."""

    def test_connected_with_ws(self) -> None:
        """Test connected property when ws is provided."""
        mock_ws = MagicMock()
        mock_ws.closed = False
        
        details = WebSocketDetails(ws=mock_ws)
        assert details.connected is True

    def test_connected_with_closed_ws(self) -> None:
        """Test connected property when ws is closed."""
        mock_ws = MagicMock()
        mock_ws.closed = True
        
        details = WebSocketDetails(ws=mock_ws)
        assert details.connected is False

    def test_connected_without_ws(self) -> None:
        """Test connected property when ws is None."""
        details = WebSocketDetails(ws=None)
        assert details.connected is False

    async def test_disconnect_with_callback(self) -> None:
        """Test disconnect with callback."""
        callback = AsyncMock()
        details = WebSocketDetails(disconnect_callback=callback)
        
        await details.disconnect()
        
        callback.assert_called_once()

    async def test_disconnect_without_callback(self) -> None:
        """Test disconnect without callback."""
        details = WebSocketDetails(disconnect_callback=None)
        
        # Should not raise an exception
        await details.disconnect()


class TestCoffeeAndFlushCounter:
    """Test CoffeeAndFlushCounter model."""

    def test_widget_type_property(self) -> None:
        """Test widget_type property."""
        counter = CoffeeAndFlushCounter(
            total_coffee=50,
            total_flush=10
        )
        
        assert counter.widget_type == WidgetType.COFFEE_AND_FLUSH_COUNTER

    def test_serialization(self) -> None:
        """Test serialization and deserialization."""
        counter = CoffeeAndFlushCounter(
            total_coffee=100,
            total_flush=25
        )
        
        # Serialize to dict (uses snake_case internally)
        serialized = counter.to_dict()
        assert serialized["total_coffee"] == 100
        assert serialized["total_flush"] == 25
        
        # Test deserialization (expects camelCase due to alias)
        data = {
            "totalCoffee": 150,
            "totalFlush": 30
        }
        deserialized = CoffeeAndFlushCounter.from_dict(data)
        assert deserialized.total_coffee == 150
        assert deserialized.total_flush == 30
        assert deserialized.widget_type == WidgetType.COFFEE_AND_FLUSH_COUNTER

    def test_counter_values(self) -> None:
        """Test counter with various values."""
        # Test with zero values
        counter = CoffeeAndFlushCounter(total_coffee=0, total_flush=0)
        assert counter.total_coffee == 0
        assert counter.total_flush == 0
        
        # Test with large values
        counter = CoffeeAndFlushCounter(total_coffee=999999, total_flush=999999)
        assert counter.total_coffee == 999999
        assert counter.total_flush == 999999