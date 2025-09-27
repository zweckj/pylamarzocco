"""Comprehensive tests for cloud client."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from pylamarzocco.clients._cloud import LaMarzoccoCloudClient
from pylamarzocco.util import InstallationKey, generate_installation_key
from pylamarzocco.models import WebSocketDetails


class TestLaMarzoccoCloudClient:
    """Test LaMarzoccoCloudClient class."""

    def test_init_with_custom_client(self) -> None:
        """Test initialization with custom client session."""
        username = "custom@example.com"
        password = "custom-password"
        installation_key = generate_installation_key("custom-install-id")
        custom_session = MagicMock()
        
        client = LaMarzoccoCloudClient(username, password, installation_key, custom_session)
        
        assert client._username == username
        assert client._password == password
        assert client._installation_key == installation_key
        assert client._client == custom_session

    def test_installation_key_storage(self) -> None:
        """Test that installation key is properly stored."""
        username = "key@example.com"
        password = "key-password"
        installation_key = generate_installation_key("unique-install-id")
        custom_session = MagicMock()
        
        client = LaMarzoccoCloudClient(username, password, installation_key, custom_session)
        
        # Should store the exact same installation key object
        assert client._installation_key is installation_key
        assert client._installation_key.installation_id == "unique-install-id"

    def test_credentials_storage(self) -> None:
        """Test that credentials are properly stored."""
        username = "creds@example.com"
        password = "secret-password-123"
        installation_key = generate_installation_key("creds-install-id")
        custom_session = MagicMock()
        
        client = LaMarzoccoCloudClient(username, password, installation_key, custom_session)
        
        # Should store credentials exactly as provided
        assert client._username == username
        assert client._password == password

    def test_access_token_initialization(self) -> None:
        """Test access token initialization."""
        username = "token@example.com"
        password = "token-password"
        installation_key = generate_installation_key("token-install-id")
        custom_session = MagicMock()
        
        client = LaMarzoccoCloudClient(username, password, installation_key, custom_session)
        
        # Should start with no access token
        assert client._access_token is None

    def test_pending_commands_dict(self) -> None:
        """Test pending commands dictionary initialization."""
        username = "cmd@example.com"
        password = "cmd-password"
        installation_key = generate_installation_key("cmd-install-id")
        custom_session = MagicMock()
        
        client = LaMarzoccoCloudClient(username, password, installation_key, custom_session)
        
        # Should start with empty pending commands
        assert isinstance(client._pending_commands, dict)
        assert len(client._pending_commands) == 0

    def test_websocket_property(self) -> None:
        """Test websocket property access."""
        username = "ws@example.com"
        password = "ws-password"
        installation_key = generate_installation_key("ws-install-id")
        custom_session = MagicMock()
        
        client = LaMarzoccoCloudClient(username, password, installation_key, custom_session)
        
        # Should have a default WebSocketDetails instance
        websocket = client.websocket
        assert isinstance(websocket, WebSocketDetails)
        assert not websocket.connected  # Should be disconnected initially

    def test_different_installation_keys(self) -> None:
        """Test clients with different installation keys are independent."""
        username = "multi@example.com"
        password = "multi-password"
        custom_session1 = MagicMock()
        custom_session2 = MagicMock()
        
        key1 = generate_installation_key("install-id-1")
        key2 = generate_installation_key("install-id-2")
        
        client1 = LaMarzoccoCloudClient(username, password, key1, custom_session1)
        client2 = LaMarzoccoCloudClient(username, password, key2, custom_session2)
        
        # Should have different installation keys
        assert client1._installation_key != client2._installation_key
        assert client1._installation_key.installation_id != client2._installation_key.installation_id
        
        # Should have independent pending commands
        assert client1._pending_commands is not client2._pending_commands
        
        # Should have independent websockets
        assert client1.websocket is not client2.websocket
        
        # Should have different client sessions
        assert client1._client != client2._client