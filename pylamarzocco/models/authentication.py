"""Models for authentication."""

from time import time
from dataclasses import dataclass, field

from mashumaro import field_options
from mashumaro.mixins.json import DataClassJSONMixin
from mashumaro.config import BaseConfig

from pylamarzocco.const import TOKEN_EXPIRATION


@dataclass(kw_only=True, frozen=True)
class AccessToken(DataClassJSONMixin):
    """Base for access token response model."""

    access_token: str = field(metadata=field_options(alias="accessToken"))
    refresh_token: str = field(metadata=field_options(alias="refreshToken"))
    expires_at: float = field(default=time() + TOKEN_EXPIRATION)

@dataclass(kw_only=True, frozen=True)
class SigninTokenRequest(DataClassJSONMixin):
    """Token request model."""

    username: str
    password: str

@dataclass(kw_only=True, frozen=True)
class RefreshTokenRequest(DataClassJSONMixin):
    """Token request model."""

    username: str
    refresh_token: str = field(metadata=field_options(alias="refreshToken"))
    class Config(BaseConfig):
        """Config for Mashumaro serialization."""
        serialize_by_alias = True