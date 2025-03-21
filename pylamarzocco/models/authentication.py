"""Models for authentication."""

from time import time
from dataclasses import dataclass, field

from mashumaro import field_options
from mashumaro.mixins.json import DataClassJSONMixin

from pylamarzocco.const import TOKEN_EXPIRATION


@dataclass(kw_only=True)
class AccessToken(DataClassJSONMixin):
    """Token response model."""

    id: str 
    access_token: str = field(metadata=field_options(alias="accessToken"))
    refresh_token: str = field(metadata=field_options(alias="refreshToken"))
    token_type: str = field(metadata=field_options(alias="tokenType"))
    username: str
    email: str
    expires_in: float = field(default=time() + TOKEN_EXPIRATION)


@dataclass(kw_only=True)
class TokenRequest(DataClassJSONMixin):
    """Token request model."""

    username: str
    password: str