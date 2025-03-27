"""Base class for all La Marzocco IoT devices."""

import logging
from typing import Any

from bleak.exc import BleakError

from pylamarzocco.clients import LaMarzoccoBluetoothClient, LaMarzoccoCloudClient
from pylamarzocco.exceptions import BluetoothConnectionFailed
from pylamarzocco.models import DashboardConfig, ThingSettings, Statistics

_LOGGER = logging.getLogger(__name__)


class LaMarzoccoThing:
    """Base class for all La Marzocco devices"""

    dashboard: DashboardConfig

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
        self.dashboard = await self.cloud_client.get_thing_dashboard(self.serial_number)

    def to_dict(self) -> dict[Any, Any]:
        """Return self in dict represenation."""
        return self.config.to_dict()
