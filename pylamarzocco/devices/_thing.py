"""Base class for all La Marzocco IoT devices."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Coroutine
from functools import wraps
from typing import Any, Concatenate

from bleak.exc import BleakError

from pylamarzocco.clients import LaMarzoccoBluetoothClient, LaMarzoccoCloudClient
from pylamarzocco.exceptions import BluetoothConnectionFailed, CloudOnlyFunctionality
from pylamarzocco.models import (
    ThingDashboardConfig,
    ThingDashboardWebsocketConfig,
    ThingSettings,
    ThingStatistics,
)

_LOGGER = logging.getLogger(__name__)


def cloud_only[_R, **P](
    func: Callable[Concatenate[LaMarzoccoThing, P], Coroutine[Any, Any, _R]],
) -> Callable[Concatenate[LaMarzoccoThing, P], Coroutine[Any, Any, _R]]:
    """Decorator to mark functionality that is only available on the cloud."""

    @wraps(func)
    async def wrapper(self: LaMarzoccoThing, *args: P.args, **kwargs: P.kwargs):
        if self.cloud_client is None:
            raise CloudOnlyFunctionality()
        return await func(self, *args, **kwargs)

    return wrapper


class LaMarzoccoThing:
    """Base class for all La Marzocco devices"""

    dashboard: ThingDashboardConfig
    settings: ThingSettings
    statistics: ThingStatistics

    def __init__(
        self,
        serial_number: str,
        cloud_client: LaMarzoccoCloudClient | None = None,
        bluetooth_client: LaMarzoccoBluetoothClient | None = None,
    ) -> None:
        """Initializes a new La Marzocco thing."""

        if cloud_client is None and bluetooth_client is None:
            raise ValueError("Need to pass at least one client")

        self.serial_number = serial_number
        self.cloud_client = cloud_client
        self.bluetooth_client = bluetooth_client
        self._update_callback: Callable[[ThingDashboardWebsocketConfig], Any] | None = (
            None
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

    @cloud_only  # TODO: Get this also from BT
    async def get_dashboard(self) -> None:
        """Get the dashboard for a thing."""
        assert self.cloud_client
        self.dashboard = await self.cloud_client.get_thing_dashboard(self.serial_number)

    @cloud_only
    async def get_settings(self) -> None:
        """Get the dashboard for a thing."""
        assert self.cloud_client
        self.settings = await self.cloud_client.get_thing_settings(self.serial_number)

    @cloud_only
    async def get_statistics(self) -> None:
        """Get the statistics for a thing."""
        assert self.cloud_client
        self.statistics = await self.cloud_client.get_thing_statistics(
            self.serial_number
        )

    def _websocket_dashboard_update_received(
        self, config: ThingDashboardWebsocketConfig
    ) -> None:
        """Handler for receiving a websocket message."""
        self.dashboard.widgets = config.widgets
        self.dashboard.config = config.config

        if self._update_callback is not None:
            self._update_callback(config)

    @cloud_only
    async def connect_dashboard_websocket(
        self,
        update_callback: Callable[[ThingDashboardWebsocketConfig], Any] | None = None,
    ) -> None:
        """Connect to the cloud websocket for the dashboard.

        Args:
            update_callback: Optional callback to be called when update is received
        """
        self._update_callback = update_callback

        await self.cloud_client.websocket_connect(
            self.serial_number, self._websocket_dashboard_update_received
        )

    def to_dict(self) -> dict[Any, Any]:
        """Return self in dict represenation."""
        return self.dashboard.to_dict()
