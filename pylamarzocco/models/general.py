"""Models for general info"""

from dataclasses import dataclass, field

from mashumaro import field_options
from mashumaro.mixins.json import DataClassJSONMixin


@dataclass(kw_only=True)
class CommandResponse(DataClassJSONMixin):
    """Response for change setting endpoint"""
    id: str
    status: str
    error_code: str | None = field(
        metadata=field_options(alias="errorCode")
    )

@dataclass(kw_only=True)
class Device(DataClassJSONMixin):
    """Generic device information returned from things endpoint"""
    serial_number: str = field(metadata=field_options(alias="serialNumber"))
    type: str
    name: str
    location: str | None
    model_code: str = field(metadata=field_options(alias="modelCode"))
    model_name: str = field(metadata=field_options(alias="modelName"))
    connected: bool
    connection_date: int = field(metadata=field_options(alias="connectionDate"))
    offline_mode: bool = field(metadata=field_options(alias="offlineMode"))
    require_firmware_update: bool = field(
        metadata=field_options(alias="requireFirmwareUpdate")
    )
    available_firmware_update: bool = field(
        metadata=field_options(alias="availableFirmwareUpdate")
    )
    coffeestation: str | None
    image_url: str = field(metadata=field_options(alias="imageUrl"))
    ble_auth_token: str | None = field(
        metadata=field_options(alias="bleAuthToken")
    )