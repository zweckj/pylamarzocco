"""Models for updating."""

from dataclasses import dataclass, field

from mashumaro import field_options
from mashumaro.mixins.json import DataClassJSONMixin

from pylamarzocco.const import (
    UpdateProgressInfo,
    UpdateStatus,
    UpdateCommandStatus,
    FirmwareType,
)


@dataclass
class UpdateDetails(DataClassJSONMixin):
    """Update status."""

    status: UpdateStatus
    command_status: UpdateCommandStatus | None = field(
        metadata=field_options(alias="commandStatus"), default=None
    )
    progress_info: UpdateProgressInfo | None = field(
        metadata=field_options(alias="progressInfo"), default=None
    )
    progress_percentage: int | None = field(
        metadata=field_options(alias="progressPercentage"), default=None
    )


@dataclass(kw_only=True)
class FirmwareVersion(DataClassJSONMixin):
    """Describes a firmware version."""

    type: FirmwareType
    build_version: str = field(metadata=field_options(alias="buildVersion"))
    change_log: str = field(metadata=field_options(alias="changeLog"))
    thing_model_code: str = field(metadata=field_options(alias="thingModelCode"))


@dataclass(kw_only=True)
class FirmwareSettings(FirmwareVersion):
    """Firmware settings configuration."""

    status: UpdateStatus
    available_update: FirmwareVersion | None = field(
        metadata=field_options(alias="availableUpdate"), default=None
    )
