"""Comprehensive tests for bluetooth client."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from bleak import BLEDevice, BleakClient, BleakScanner

from pylamarzocco.clients._bluetooth import LaMarzoccoBluetoothClient
from pylamarzocco.exceptions import BluetoothConnectionFailed


class TestLaMarzoccoBluetoothClient:
    """Test LaMarzoccoBluetoothClient class."""

    def test_init_with_ble_device(self) -> None:
        """Test initialization with BLEDevice."""
        ble_device = MagicMock(spec=BLEDevice)
        ble_device.address = "00:11:22:33:44:55"
        token = "test-token-123"
        
        client = LaMarzoccoBluetoothClient(ble_device, token)
        
        assert client._ble_token == token
        assert client._address == "00:11:22:33:44:55"
        assert client._address_or_ble_device == ble_device

    def test_init_with_address_string(self) -> None:
        """Test initialization with address string."""
        address = "AA:BB:CC:DD:EE:FF"
        token = "test-token-456"
        
        client = LaMarzoccoBluetoothClient(address, token)
        
        assert client._ble_token == token
        assert client._address == address
        assert client._address_or_ble_device == address

    @patch('pylamarzocco.clients._bluetooth.BleakClient')
    async def test_context_manager_connect_success(self, mock_bleak_client_class) -> None:
        """Test successful connection using context manager."""
        mock_client = AsyncMock(spec=BleakClient)
        mock_bleak_client_class.return_value = mock_client
        
        # Mock the authentication method
        address = "00:11:22:33:44:55"
        token = "test-token"
        
        bluetooth_client = LaMarzoccoBluetoothClient(address, token)
        
        # Mock the authenticate method
        with patch.object(bluetooth_client, '_authenticate', new_callable=AsyncMock):
            async with bluetooth_client as client:
                assert client == bluetooth_client
                mock_client.connect.assert_called_once()
            
            mock_client.disconnect.assert_called_once()

    @patch('pylamarzocco.clients._bluetooth.BleakClient')
    async def test_context_manager_connect_failure(self, mock_bleak_client_class) -> None:
        """Test connection failure using context manager."""
        mock_client = AsyncMock(spec=BleakClient)
        mock_client.connect.side_effect = Exception("Connection failed")
        mock_bleak_client_class.return_value = mock_client
        
        address = "00:11:22:33:44:55"
        token = "test-token"
        
        bluetooth_client = LaMarzoccoBluetoothClient(address, token)
        
        with pytest.raises(Exception, match="Connection failed"):
            async with bluetooth_client:
                pass

    @patch('pylamarzocco.clients._bluetooth.BleakScanner')
    async def test_discover_devices_with_default_scanner(self, mock_scanner_class) -> None:
        """Test discover_devices with default scanner."""
        mock_scanner = AsyncMock(spec=BleakScanner)
        mock_scanner_class.return_value = mock_scanner
        
        # Create mock devices
        device1 = MagicMock(spec=BLEDevice)
        device1.name = "MICRA01234"
        device1.address = "00:11:22:33:44:55"
        
        device2 = MagicMock(spec=BLEDevice)
        device2.name = "OtherDevice"
        device2.address = "AA:BB:CC:DD:EE:FF"
        
        device3 = MagicMock(spec=BLEDevice)
        device3.name = "MINI56789"  
        device3.address = "11:22:33:44:55:66"
        
        mock_scanner.discover.return_value = [device1, device2, device3]
        
        devices = await LaMarzoccoBluetoothClient.discover_devices()
        
        # Should only return devices with names starting with MICRA, MINI, or GS3
        assert len(devices) == 2
        assert device1 in devices
        assert device3 in devices
        assert device2 not in devices
        
        mock_scanner_class.assert_called_once()
        mock_scanner.discover.assert_called_once()

    async def test_discover_devices_with_custom_scanner(self) -> None:
        """Test discover_devices with custom scanner."""
        mock_scanner = AsyncMock()
        
        # Create mock devices
        device1 = MagicMock(spec=BLEDevice)
        device1.name = "GS398765"
        device1.address = "FF:EE:DD:CC:BB:AA"
        
        mock_scanner.discover.return_value = [device1]
        
        devices = await LaMarzoccoBluetoothClient.discover_devices(mock_scanner)
        
        assert len(devices) == 1
        assert devices[0] == device1
        mock_scanner.discover.assert_called_once()

    async def test_discover_devices_no_matching_devices(self) -> None:
        """Test discover_devices when no La Marzocco devices found."""
        mock_scanner = AsyncMock()
        
        # Create mock devices without LM prefix
        device1 = MagicMock(spec=BLEDevice)
        device1.name = "SomeOtherDevice"
        
        device2 = MagicMock(spec=BLEDevice)
        device2.name = None  # Device with no name
        
        mock_scanner.discover.return_value = [device1, device2]
        
        devices = await LaMarzoccoBluetoothClient.discover_devices(mock_scanner)
        
        assert len(devices) == 0

    async def test_discover_devices_device_with_none_name(self) -> None:
        """Test discover_devices handles devices with None name."""
        mock_scanner = AsyncMock()
        
        # Create mock devices, some with None names
        device1 = MagicMock(spec=BLEDevice)
        device1.name = None
        
        device2 = MagicMock(spec=BLEDevice)
        device2.name = "MICRA12345"
        
        device3 = MagicMock(spec=BLEDevice)
        device3.name = ""  # Empty string name
        
        mock_scanner.discover.return_value = [device1, device2, device3]
        
        devices = await LaMarzoccoBluetoothClient.discover_devices(mock_scanner)
        
        # Should only return device2 which has a valid La Marzocco name
        assert len(devices) == 1
        assert devices[0] == device2

    def test_client_address_property_access(self) -> None:
        """Test accessing client address after initialization."""
        address = "12:34:56:78:90:AB"
        token = "test-access-token"
        
        client = LaMarzoccoBluetoothClient(address, token)
        
        # Test that we can access the address
        assert client._address == address
        assert client._ble_token == token