"""Base class for all La Marzocco IoT devices."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from bleak.exc import BleakError

from pylamarzocco.clients import LaMarzoccoBluetoothClient, LaMarzoccoCloudClient
from pylamarzocco.exceptions import BluetoothConnectionFailed
from pylamarzocco.models import DashboardDeviceConfig, ThingSettings, ThingStatistics

_LOGGER = logging.getLogger(__name__)


class LaMarzoccoThing:
    """Base class for all La Marzocco devices"""

    dashboard: DashboardDeviceConfig
    settings: ThingSettings
    statistics: ThingStatistics

    def __init__(
        self,
        serial_number: str,
        cloud_client: LaMarzoccoCloudClient | None = None,
        bluetooth_client: LaMarzoccoBluetoothClient | None = None,
    ) -> None:
        """Initializes a new LaMarzocco thing."""

        self.serial_number = serial_number
        self.cloud_client = cloud_client
        self.bluetooth_client = bluetooth_client

    @classmethod
    async def create(
        cls,
        serial_number: str,
        cloud_client: LaMarzoccoCloudClient | None = None,
        bluetooth_client: LaMarzoccoBluetoothClient | None = None,
    ) -> LaMarzoccoThing:
        """Initialize a client with all data."""

        self = cls(serial_number, cloud_client, bluetooth_client)
        await asyncio.gather(
            self.get_dashboard(), self.get_settings(), self.get_statistics()
        )

    async def _bluetooth_command_with_cloud_fallback(
        self,
        command: str,
        **kwargs,
    ) -> bool:
        """Send a command to the machine via Bluetooth, falling back to cloud if necessary."""

        # First, try with bluetooth
        if self.bluetooth_client is not None:
            func = getattr(self.bluetooth_client, command)
            try:
                _LOGGER.debug(
                    "Sending command %s over bluetooth with params %s",
                    command,
                    str(kwargs),
                )
                await func(**kwargs)
            except (BleakError, BluetoothConnectionFailed) as exc:
                msg = "Could not send command to bluetooth device, even though initalized."

                if self.cloud_client is None:
                    _LOGGER.error(
                        "%s Cloud client not initialized, cannot fallback. Full error %s",
                        msg,
                        exc,
                    )
                    return False

                _LOGGER.warning("%s Falling back to cloud", msg)
                _LOGGER.debug("Full error: %s", exc)
            else:
                return True

        # no bluetooth or failed, try with cloud
        if self.cloud_client is not None:
            _LOGGER.debug(
                "Sending command %s over cloud with params %s",
                command,
                str(kwargs),
            )
            func = getattr(self.cloud_client, command)
            kwargs["serial_number"] = self.serial_number
            if await func(**kwargs):
                return True
        return False

    async def get_dashboard(self) -> None:
        """Get the dashboard for a thing."""
        self.dashboard = await self.cloud_client.get_thing_dashboard(self.serial_number)

    async def get_settings(self) -> None:
        """Get the dashboard for a thing."""
        self.settings = await self.cloud_client.get_thing_settings(self.serial_number)

    async def get_statistics(self) -> None:
        """Get the statistics for a thing."""
        self.statistics = await self.cloud_client.get_thing_statistics(
            self.serial_number
        )

    def to_dict(self) -> dict[Any, Any]:
        """Return self in dict represenation."""
        return self.dashboard.to_dict()
