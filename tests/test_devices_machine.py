"""Test LaMarzoccoMachine class."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from pylamarzocco.devices._machine import LaMarzoccoMachine
from pylamarzocco.clients import LaMarzoccoBluetoothClient, LaMarzoccoCloudClient
from pylamarzocco.models import ThingSchedulingSettings
from pylamarzocco.exceptions import CloudOnlyFunctionality


class TestLaMarzoccoMachine:
    """Test LaMarzoccoMachine class."""

    def test_init_with_no_clients(self) -> None:
        """Test initialization without any clients."""
        serial = "machine-serial-123"
        machine = LaMarzoccoMachine(serial)
        
        assert machine.serial_number == serial
        assert machine._cloud_client is None
        assert machine._bluetooth_client is None
        assert isinstance(machine.schedule, ThingSchedulingSettings)
        assert machine.schedule.serial_number == serial

    def test_init_with_cloud_client(self) -> None:
        """Test initialization with cloud client."""
        serial = "machine-serial-456"
        cloud_client = MagicMock(spec=LaMarzoccoCloudClient)
        
        machine = LaMarzoccoMachine(serial, cloud_client=cloud_client)
        
        assert machine.serial_number == serial
        assert machine._cloud_client == cloud_client
        assert machine._bluetooth_client is None

    def test_init_with_bluetooth_client(self) -> None:
        """Test initialization with bluetooth client."""
        serial = "machine-serial-789"
        bluetooth_client = MagicMock(spec=LaMarzoccoBluetoothClient)
        
        machine = LaMarzoccoMachine(serial, bluetooth_client=bluetooth_client)
        
        assert machine.serial_number == serial
        assert machine._cloud_client is None
        assert machine._bluetooth_client == bluetooth_client

    async def test_get_schedule_with_cloud_client(self) -> None:
        """Test get_schedule with cloud client."""
        serial = "machine-schedule-test"
        cloud_client = AsyncMock(spec=LaMarzoccoCloudClient)
        mock_schedule = MagicMock(spec=ThingSchedulingSettings)
        cloud_client.get_thing_schedule.return_value = mock_schedule
        
        machine = LaMarzoccoMachine(serial, cloud_client=cloud_client)
        
        await machine.get_schedule()
        
        cloud_client.get_thing_schedule.assert_called_once_with(serial)
        assert machine.schedule == mock_schedule

    async def test_get_schedule_without_cloud_client(self) -> None:
        """Test get_schedule without cloud client raises exception."""
        serial = "machine-no-cloud"
        machine = LaMarzoccoMachine(serial)
        
        with pytest.raises(CloudOnlyFunctionality):
            await machine.get_schedule()

    async def test_set_steam_with_cloud_client(self) -> None:
        """Test set_steam with cloud client."""
        serial = "machine-steam-test"
        cloud_client = AsyncMock(spec=LaMarzoccoCloudClient)
        cloud_client.set_steam.return_value = True
        
        machine = LaMarzoccoMachine(serial, cloud_client=cloud_client)
        
        result = await machine.set_steam(True)
        
        assert result is True
        cloud_client.set_steam.assert_called_once_with(serial_number=serial, enabled=True)

    async def test_set_steam_with_false(self) -> None:
        """Test set_steam with False parameter."""
        serial = "machine-steam-off"
        cloud_client = AsyncMock(spec=LaMarzoccoCloudClient)
        cloud_client.set_steam.return_value = False
        
        machine = LaMarzoccoMachine(serial, cloud_client=cloud_client)
        
        result = await machine.set_steam(False)
        
        assert result is False
        cloud_client.set_steam.assert_called_once_with(serial_number=serial, enabled=False)

    async def test_set_steam_without_any_client(self) -> None:
        """Test set_steam without any client returns False."""
        serial = "machine-no-clients"
        machine = LaMarzoccoMachine(serial)
        
        # set_steam now uses bluetooth_command_with_cloud_fallback
        # which returns False when no clients are available
        result = await machine.set_steam(True)
        assert result is False

    def test_inheritance_from_thing(self) -> None:
        """Test that machine inherits properly from LaMarzoccoThing."""
        serial = "machine-inheritance"
        machine = LaMarzoccoMachine(serial)
        
        # Should have all the attributes from LaMarzoccoThing
        assert hasattr(machine, 'dashboard')
        assert hasattr(machine, 'settings')
        assert hasattr(machine, 'statistics')
        assert hasattr(machine, 'websocket')
        
        # Plus the machine-specific schedule attribute
        assert hasattr(machine, 'schedule')
        assert isinstance(machine.schedule, ThingSchedulingSettings)