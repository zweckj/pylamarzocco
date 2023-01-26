from .const import *
from .credentials import Credentials
from .exceptions import *
from .lmlocalapi import LMLocalAPI
from authlib.integrations.base_client.errors import OAuthError
from authlib.integrations.httpx_client import AsyncOAuth2Client


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

    def __init__(self):
        pass

    @classmethod
    async def create(cls, credentials: Credentials, ip, port):
        self = cls()
        self.client = await self._connect(credentials)
        self._machine_info = await self._get_machine_info()
        self._lm_local_api = LMLocalAPI(local_ip=ip, local_port=port, local_bearer=self.machine_info[KEY])
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

    '''
    Turn Steamboiler on or off
    '''
    async def set_steam(self, steam_state):
        if not type(steam_state) == bool:
            print("Steam state must be boolean")
            exit(1)
        else:
            data = {"identifier": STEAM_BOILER_NAME, "state": steam_state}
            url = f"{GW_MACHINE_BASE_URL}/{self.machine_info[SERIAL_NUMBER]}/enable-boiler"
            response = await self.client.post(url, json=data)
            return response

    '''
    Set steamboiler temperature (in Celsius)
    '''
    async def set_steam_temp(self, temperature):
        if not type(temperature) == int:
            print("Steam temp must be integer")  
            exit(1)
        elif not temperature == 131 and not temperature == 128 and not temperature == 126:
            print("Steam temp must be one of 126, 128, 131 (°C)")
            exit(1)
        else:
            data = { "identifier": STEAM_BOILER_NAME, "value": temperature}
            url = f"{GW_MACHINE_BASE_URL}/{self.machine_info[SERIAL_NUMBER]}/target-boiler"
            response = await self.client.post(url, json=data)
            return response

    '''
    Set coffee boiler temperature (in Celsius)
    '''
    async def set_coffee_temp(self, temperature):

        if temperature > 104 or temperature < 85:
            print("Coffee temp must be between 85 and 104 (°C)")
            exit(1)
        else:
            temperature = round(temperature, 1)
            data = { "identifier": COFFEE_BOILER_NAME, "value": temperature}
            url = f"{GW_MACHINE_BASE_URL}/{self.machine_info[SERIAL_NUMBER]}/target-boiler"
            response = await self.client.post(url, json=data)
            return response