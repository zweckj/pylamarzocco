from .const import *
from .credentials import Credentials
from .exceptions import *
from authlib.integrations.base_client.errors import OAuthError
from authlib.integrations.httpx_client import AsyncOAuth2Client

class LMCloud:  

    @property
    def _client(self):
        return self._client

    @_client.setter
    def _client(self, value):
        if type(value) != AsyncOAuth2Client:
            raise TypeError
        self._client = value

    @property
    def _machine_info(self):
        return self._machine_info

    '''
    Establish connection by building the OAuth client and requesting the token
    '''
    async def _connect(self, Credentials):
        async with AsyncOAuth2Client(
            client_id=Credentials.client_id,
            client_secret=Credentials.client_secret,
            token_endpoint=TOKEN_URL,
        ) as client:

            headers = {
                "client_id": Credentials.client_id,
                "client_secret": Credentials.client_secret,
            }

            try:
                await client.fetch_token(
                    url=TOKEN_URL,
                    username=Credentials.username,
                    password=Credentials.password,
                    headers=headers,
                )
                
                return client
        
            except OAuthError as err:
                raise AuthFail("Authorization failure") from err

    async def _get_machine_info(self):
        response = await self._client.get(CUSTOMER_URL)

    async def __init__(self, Credentials):
        self._client = await self._connect(Credentials)

    def set_power(self):
        self._client.post()