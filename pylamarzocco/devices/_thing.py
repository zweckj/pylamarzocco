"""Base class for all La Marzocco IoT devices."""

from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from functools import wraps
from typing import Any, Concatenate

from pylamarzocco.clients import LaMarzoccoBluetoothClient, LaMarzoccoCloudClient
from pylamarzocco.const import ModelCode
from pylamarzocco.exceptions import (
    CloudOnlyFunctionality,
    UnsupportedModel,
)
from pylamarzocco.models import (
    ThingDashboardConfig,
    ThingDashboardWebsocketConfig,
    ThingSettings,
    ThingStatistics,
    UpdateDetails,
    WebSocketDetails,
)

_LOGGER = logging.getLogger(__name__)


def cloud_only[T: "LaMarzoccoThing", _R, **P](
    func: Callable[Concatenate[T, P], Coroutine[Any, Any, _R]],
) -> Callable[Concatenate[T, P], Coroutine[Any, Any, _R]]:
    """Decorator to mark functionality that is only available on the cloud."""

    @wraps(func)
    async def wrapper(self: T, *args: P.args, **kwargs: P.kwargs):
        if self._cloud_client is None:  # pylint: disable=protected-access
            raise CloudOnlyFunctionality()
        return await func(self, *args, **kwargs)

    return wrapper


def models_supported[T: "LaMarzoccoThing", _R, **P](
    supported_models: tuple[ModelCode, ...],
) -> Callable[
    [Callable[Concatenate[T, P], Coroutine[Any, Any, _R]]],
    Callable[Concatenate[T, P], Coroutine[Any, Any, _R]],
]:
    """Decorator to mark functionality only available on specific machine models.

    Args:
        supported_models: Tuple of ModelCode enums that support this functionality
    """

    def decorator(
        func: Callable[Concatenate[T, P], Coroutine[Any, Any, _R]],
    ) -> Callable[Concatenate[T, P], Coroutine[Any, Any, _R]]:
        @wraps(func)
        async def wrapper(self: T, *args: P.args, **kwargs: P.kwargs) -> _R:
            if (
                not hasattr(self, "dashboard")
                or self.dashboard.model_code not in supported_models
            ):
                supported_names = ", ".join(model.name for model in supported_models)
                raise UnsupportedModel(
                    f"This functionality is only supported on: {supported_names}."
                )
            return await func(self, *args, **kwargs)

        return wrapper

    return decorator


class LaMarzoccoThing:
    """Base class for all La Marzocco devices"""

    def __init__(
        self,
        serial_number: str,
        cloud_client: LaMarzoccoCloudClient | None = None,
        bluetooth_client: LaMarzoccoBluetoothClient | None = None,
    ) -> None:
        """Initializes a new La Marzocco thing."""

        self.serial_number = serial_number
        self._cloud_client = cloud_client
        self._bluetooth_client = bluetooth_client
        self._update_callback: Callable[[ThingDashboardWebsocketConfig], Any] | None = (
            None
        )
        self.dashboard = ThingDashboardConfig(serial_number=serial_number)
        self.settings = ThingSettings(serial_number=serial_number)
        self.statistics = ThingStatistics(serial_number=serial_number)

    @property
    def websocket(self) -> WebSocketDetails:
        """Return the status of the websocket."""
        if self._cloud_client is None:
            return WebSocketDetails()
        return self._cloud_client.websocket

    @cloud_only
    async def get_dashboard(self) -> None:
        """Get the dashboard for a thing."""
        assert self._cloud_client
        self.dashboard = await self._cloud_client.get_thing_dashboard(
            self.serial_number
        )

    @cloud_only
    async def get_settings(self) -> None:
        """Get the dashboard for a thing."""
        assert self._cloud_client
        self.settings = await self._cloud_client.get_thing_settings(self.serial_number)

    @cloud_only
    async def get_statistics(self) -> None:
        """Get the statistics for a thing."""
        assert self._cloud_client
        self.statistics = await self._cloud_client.get_thing_statistics(
            self.serial_number
        )

    @cloud_only
    async def get_firmware(self) -> UpdateDetails:
        """Get the firmware details for a thing."""
        assert self._cloud_client
        return await self._cloud_client.get_thing_firmware(self.serial_number)

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
        connect_callback: Callable[[], Any] | None = None,
        disconnect_callback: Callable[[], Any] | None = None,
        auto_reconnect: bool = True,
    ) -> None:
        """Connect to the cloud websocket for the dashboard.

        Args:
            update_callback: Optional callback to be called when update is received
        """
        assert self._cloud_client
        self._update_callback = update_callback

        await self._cloud_client.websocket_connect(
            serial_number=self.serial_number,
            notification_callback=self._websocket_dashboard_update_received,
            connect_callback=connect_callback,
            disconnect_callback=disconnect_callback,
            auto_reconnect=auto_reconnect,
        )

    @cloud_only
    async def update_firmware(self) -> None:
        """Start the firmware update process"""
        assert self._cloud_client
        await self._cloud_client.update_firmware(self.serial_number)

    def to_dict(self) -> dict[Any, Any]:
        """Return self in dict represenation."""
        return {
            "serial_number": self.serial_number,
            "dashboard": self.dashboard.to_dict() if self.dashboard else None,
            "settings": self.settings.to_dict() if self.settings else None,
            "statistics": self.statistics.to_dict() if self.statistics else None,
        }
