"""Models for general info"""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Annotated, Any, ClassVar

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

_LOGGER = logging.getLogger(__name__)


def from_epoch_ms(ts: float) -> datetime:
    """Convert a millisecond epoch timestamp to a UTC datetime."""
    return datetime.fromtimestamp(ts / 1000, timezone.utc)


def filter_valid_widgets(
    items: list[dict[str, Any] | str], field_name: str
) -> list[dict[str, Any] | str]:
    """Filter items with valid WidgetType codes, logging warnings for invalid ones.

    Args:
        items: List of widget dicts or code strings
        field_name: Name of the field being filtered (for logging)

    Returns:
        List of items with valid widget codes
    """
    valid_items = []
    for item in items:
        # Extract code - either directly if string, or from 'code' key if dict
        if code := (item if isinstance(item, str) else item.get("code")):
            try:
                WidgetType(code)
            except ValueError:
                # Log entire JSON if it's a dict, otherwise just the code
                if isinstance(item, dict):
                    _LOGGER.warning(
                        "Unknown widget in field '%s' will be discarded: %s",
                        field_name,
                        json.dumps(item),
                    )
                else:
                    _LOGGER.warning(
                        "Unknown widget code '%s' in field '%s' will be discarded",
                        code,
                        field_name,
                    )
            else:
                valid_items.append(item)
    return valid_items


def prepare_widgets(d: dict[str, Any], field_name: str) -> None:
    """Drop unknown widgets and set the output discriminator on the rest."""
    valid_widgets = filter_valid_widgets(d.get(field_name, []), field_name)
    for item in valid_widgets:
        assert isinstance(item, dict)
        item["output"]["widget_type"] = item["code"]
    d[field_name] = valid_widgets


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
            deserialize=from_epoch_ms,
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
    shot_counter_supported: bool = field(
        metadata=field_options(
            alias="shotCounterSupported", deserialize=lambda v: bool(v)
        ),
        default=False,
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

    widget_type: ClassVar[WidgetType]


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
