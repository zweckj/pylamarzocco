from .const import *
from .credentials import Credentials
from .exceptions import *
from authlib.integrations.base_client.errors import OAuthError
from authlib.integrations.httpx_client import AsyncOAuth2Client
import requests

class LMCloud:  

    @property
    def client(self):
        return self._client

    @client.setter
    def client(self, value: AsyncOAuth2Client):
        self._client = value

    @property
    def machine_info(self):
        return self._machine_info

    @property
    def local_port(self):
        return self._local_port
    
    @property
    def local_ip(self):
        return self._local_ip

    # current power status / machine mode (on/standby)
    @property
    def machine_mode(self):
        return self.local_get_config()[MACHINE_MODE]

    def __init__(self, ip, port):
        self._local_ip = ip
        self._local_port = port


    @classmethod
    async def create(cls, credentials: Credentials, ip, port):
        self = cls(ip, port)
        self.client = await self._connect(credentials)
        self._machine_info = await self._get_machine_info()
        return self
        
    '''
    Establish connection by building the OAuth client and requesting the token
    '''
    async def _connect(self, credentials: Credentials):
        client = AsyncOAuth2Client(
            client_id=credentials.client_id,
            client_secret=credentials.client_secret,
            token_endpoint=TOKEN_URL,
        )

        headers = {
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
        }

        try:
            await client.fetch_token(
                url=TOKEN_URL,
                username=credentials.username,
                password=credentials.password,
                headers=headers,
            )
            return client
    
        except OAuthError as err:
            raise AuthFail("Authorization failure") from err

    async def _get_machine_info(self):
        response = await self.client.get(CUSTOMER_URL)
        if response.status_code == 200:
            machine_info = {}
            fleet = response.json()["data"]["fleet"][0]
            machine_info[KEY] = fleet["communicationKey"]
            machine_info[SERIAL_NUMBER] = fleet["machine"]["serialNumber"]
            machine_info[MACHINE_NAME] = fleet["name"]
            machine_info[MODEL_NAME] = fleet["machine"]["model"]["name"]
            return machine_info


    '''
    Get current config of machine from local API
    '''
    def local_get_config(self):
        headers = {"Authorization": f"Bearer {self.machine_info[KEY]}"}
        response = requests.get(f"http://{self._local_ip}:{self._local_port}/api/v1/config", headers=headers)
        if response.status_code == 200:
            return response.json()["data"]

    '''
    Turn power of machine on or off
    '''
    async def set_power(self, power_status):
        power_status = str.upper(power_status)
        if not power_status in ["ON", "STANDBY"]:
            print("Power status can only be on or standby")
            exit(1)
        else:
            data = {"status": power_status}
            url = f"{GW_MACHINE_BASE_URL}/{self.machine_info[SERIAL_NUMBER]}/status"
            print(url)
            response = await self.client.post(url, json=data)
            return response