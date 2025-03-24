"""Models for general info"""

from dataclasses import dataclass, field
from datetime import datetime, timezone

from mashumaro import field_options
from mashumaro.mixins.json import DataClassJSONMixin

from pylamarzocco.const import DeviceType, ModelCode


@dataclass(kw_only=True)
class CommandResponse(DataClassJSONMixin):
    """Response for change setting endpoint"""

    id: str
    status: str
    error_code: str | None = field(
        metadata=field_options(alias="errorCode"), default=None
    )


@dataclass(kw_only=True)
class Device(DataClassJSONMixin):
    """Generic device information t"""

    serial_number: str = field(metadata=field_options(alias="serialNumber"))
    type: DeviceType
    name: str
    location: str | None = field(default=None)
    model_code: ModelCode = field(metadata=field_options(alias="modelCode"))
    model_name: str = field(metadata=field_options(alias="modelName"))
    connected: bool
    connection_date: datetime = field(
        metadata=field_options(
            alias="connectionDate",
            deserialize=lambda ts: datetime.fromtimestamp(ts / 1000, timezone.utc),
        )
    )
    offline_mode: bool = field(metadata=field_options(alias="offlineMode"))
    require_firmware_update: bool = field(
        metadata=field_options(alias="requireFirmwareUpdate"), default=False
    )
    available_firmware_update: bool = field(
        metadata=field_options(alias="availableFirmwareUpdate"), default=False
    )
    coffee_station: dict | None = field(
        metadata=field_options(alias="coffeeStation"), default=None
    )
    image_url: str = field(metadata=field_options(alias="imageUrl"))
    ble_auth_token: str | None = field(
        metadata=field_options(alias="bleAuthToken"), default=None
    )
