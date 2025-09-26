"""Tests for WebSocketDetails model."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from pylamarzocco.models import WebSocketDetails


class TestWebSocketDetails:
    """Test WebSocketDetails model."""

    def test_websocket_details_init_no_params(self) -> None:
        """Test WebSocketDetails initialization with no parameters."""
        details = WebSocketDetails()
        
        assert details._ws is None
        assert details._disconnect_callback is None
        assert not details.connected

    def test_websocket_details_init_with_ws(self) -> None:
        """Test WebSocketDetails initialization with websocket."""
        mock_ws = MagicMock()
        mock_ws.closed = False
        
        details = WebSocketDetails(ws=mock_ws)
        
        assert details._ws is mock_ws
        assert details._disconnect_callback is None
        assert details.connected

    def test_websocket_details_init_with_callback(self) -> None:
        """Test WebSocketDetails initialization with disconnect callback."""
        mock_callback = AsyncMock()
        
        details = WebSocketDetails(disconnect_callback=mock_callback)
        
        assert details._ws is None
        assert details._disconnect_callback is mock_callback
        assert not details.connected

    def test_websocket_details_init_with_both(self) -> None:
        """Test WebSocketDetails initialization with both parameters."""
        mock_ws = MagicMock()
        mock_ws.closed = False
        mock_callback = AsyncMock()
        
        details = WebSocketDetails(ws=mock_ws, disconnect_callback=mock_callback)
        
        assert details._ws is mock_ws
        assert details._disconnect_callback is mock_callback
        assert details.connected

    def test_connected_property_ws_none(self) -> None:
        """Test connected property when websocket is None."""
        details = WebSocketDetails()
        
        assert not details.connected

    def test_connected_property_ws_not_closed(self) -> None:
        """Test connected property when websocket is not closed."""
        mock_ws = MagicMock()
        mock_ws.closed = False
        
        details = WebSocketDetails(ws=mock_ws)
        
        assert details.connected

    def test_connected_property_ws_closed(self) -> None:
        """Test connected property when websocket is closed."""
        mock_ws = MagicMock()
        mock_ws.closed = True
        
        details = WebSocketDetails(ws=mock_ws)
        
        assert not details.connected

    async def test_disconnect_with_callback(self) -> None:
        """Test disconnect method with callback."""
        mock_callback = AsyncMock()
        details = WebSocketDetails(disconnect_callback=mock_callback)
        
        await details.disconnect()
        
        mock_callback.assert_called_once()

    async def test_disconnect_without_callback(self) -> None:
        """Test disconnect method without callback."""
        details = WebSocketDetails()
        
        # Should not raise an exception
        await details.disconnect()

    async def test_disconnect_callback_called_once_only(self) -> None:
        """Test that disconnect callback is only called once per call."""
        mock_callback = AsyncMock()
        details = WebSocketDetails(disconnect_callback=mock_callback)
        
        await details.disconnect()
        await details.disconnect()
        
        # Should be called twice (once for each disconnect call)
        assert mock_callback.call_count == 2

    def test_websocket_state_changes(self) -> None:
        """Test websocket connection state changes."""
        mock_ws = MagicMock()
        details = WebSocketDetails(ws=mock_ws)
        
        # Initially not closed
        mock_ws.closed = False
        assert details.connected
        
        # Now closed
        mock_ws.closed = True
        assert not details.connected
        
        # Not closed again
        mock_ws.closed = False
        assert details.connected