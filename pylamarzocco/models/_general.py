"""Models for general info"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Annotated

from aiohttp import ClientWebSocketResponse
from mashumaro import field_options
from mashumaro.mixins.json import DataClassJSONMixin
from mashumaro.types import Discriminator

from pylamarzocco.const import (
    CommandStatus,
    DeviceType,
    ModelCode,
    ModelName,
    WidgetType,
)


@dataclass(kw_only=True)
class CommandResponse(DataClassJSONMixin):
    """Response for change setting endpoint"""

    id: str
    status: CommandStatus
    error_code: str | None = field(
        metadata=field_options(alias="errorCode"), default=None
    )


@dataclass(kw_only=True)
class Thing(DataClassJSONMixin):
    """Generic device information."""

    serial_number: str = field(metadata=field_options(alias="serialNumber"))
    type: DeviceType = field(default=DeviceType.MACHINE)
    name: str = field(default="")
    location: str | None = field(default=None)
    model_code: ModelCode = field(
        metadata=field_options(alias="modelCode"), default=ModelCode.LINEA_MICRA
    )
    model_name: ModelName = field(
        metadata=field_options(
            alias="modelName", deserialize=lambda n: ModelName.from_string(str(n))
        ),
        default=ModelName.LINEA_MICRA,
    )
    connected: bool = field(default=False)
    connection_date: datetime = field(
        metadata=field_options(
            alias="connectionDate",
            deserialize=lambda ts: datetime.fromtimestamp(ts / 1000, timezone.utc),
        ),
        default=datetime.now(timezone.utc),
    )
    offline_mode: bool = field(
        metadata=field_options(alias="offlineMode"), default=False
    )
    require_firmware_update: bool = field(
        metadata=field_options(alias="requireFirmwareUpdate"), default=False
    )
    available_firmware_update: bool = field(
        metadata=field_options(alias="availableFirmwareUpdate"), default=False
    )
    coffee_station: dict | None = field(
        metadata=field_options(alias="coffeeStation"), default=None
    )
    image_url: str = field(metadata=field_options(alias="imageUrl"), default="")
    ble_auth_token: str | None = field(
        metadata=field_options(alias="bleAuthToken"), default=None
    )


@dataclass(kw_only=True)
class BaseWidget(DataClassJSONMixin):
    """Base widget configuration."""

    code: WidgetType
    index: int


@dataclass(kw_only=True)
class Widget(BaseWidget):
    """Widget configuration."""

    output: Annotated[
        BaseWidgetOutput, Discriminator(field="widget_type", include_subtypes=True)
    ]


@dataclass(kw_only=True)
class BaseWidgetOutput(DataClassJSONMixin):
    """Widget configuration."""


class WebSocketDetails:
    """Hold the websocket connection."""

    def __init__(
        self,
        ws: ClientWebSocketResponse | None = None,
        disconnect_callback: Callable[[], Awaitable] | None = None,
    ):
        """Initialize the class.

        Args:
            disconnect_callback: Callback to call to actively disconnect from WS
        """
        self._disconnect_callback: Callable[[], Awaitable] | None = disconnect_callback
        self._ws = ws

    @property
    def connected(self) -> bool:
        """Return the connection status of the ws."""
        if self._ws is None:
            return False
        return not self._ws.closed

    async def disconnect(self) -> None:
        """Disconnect from the websocket."""
        if self._disconnect_callback:
            await self._disconnect_callback()
