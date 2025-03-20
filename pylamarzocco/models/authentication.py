"""Models for authentication."""

from dataclasses import dataclass, field

from mashumaro import field_options
from mashumaro.mixins.json import DataClassJSONMixin


@dataclass(kw_only=True)
class TokenResponse(DataClassJSONMixin):
    """Token response model."""

    id: str 
    access_token: str = field(metadata=field_options(alias="accessToken"))
    refresh_token: str = field(metadata=field_options(alias="refreshToken"))
    token_type: str = field(metadata=field_options(alias="tokenType"))
    username: str
    email: str


@dataclass(kw_only=True)
class TokenRequest(DataClassJSONMixin):
    """Token request model."""

    username: str
    password: str