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