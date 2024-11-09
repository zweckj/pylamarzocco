"""Example implementation of a La Marzocco Cloud Client using Authlib."""

from authlib.common.errors import AuthlibHTTPError  # type: ignore[import]
from authlib.integrations.base_client.errors import OAuthError  # type: ignore[import]
from authlib.integrations.httpx_client import AsyncOAuth2Client  # type: ignore[import]

from pylamarzocco.client_cloud import LaMarzoccoCloudClient
from pylamarzocco.const import DEFAULT_CLIENT_ID, DEFAULT_CLIENT_SECRET, TOKEN_URL
from pylamarzocco.exceptions import AuthFail, RequestNotSuccessful


class LaMarzoccoAuthlibCloudClient(LaMarzoccoCloudClient):
    """La Marzocco Cloud Client using Authlib."""

    _client: AsyncOAuth2Client

    def __init__(self, username: str, password: str) -> None:
        self.username = username
        self.password = password
        client = AsyncOAuth2Client(
            client_id=DEFAULT_CLIENT_ID,
            client_secret=DEFAULT_CLIENT_SECRET,
            token_endpoint=TOKEN_URL,
        )
        super().__init__(client)

    async def async_get_access_token(self) -> str:
        try:
            await self._client.fetch_token(
                url=TOKEN_URL,
                username=self.username,
                password=self.password,
            )
        except OAuthError as exc:
            raise AuthFail(f"Authorization failure: {exc}") from exc
        except AuthlibHTTPError as exc:
            raise RequestNotSuccessful(
                f"Exception during token request: {exc}"
            ) from exc

        # make sure oauth token is still valid
        if self._client.token.is_expired():
            await self._client.refresh_token(TOKEN_URL)
        return ""
