"""Models for authentication."""

from dataclasses import dataclass, field
from time import time

from mashumaro import field_options
from mashumaro.config import BaseConfig
from mashumaro.mixins.json import DataClassJSONMixin

TOKEN_EXPIRATION = 60 * 60 # 1 hour

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