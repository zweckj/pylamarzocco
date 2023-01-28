from .const import *
from .credentials import Credentials
from .exceptions import *
from .lmlocalapi import LMLocalAPI
from .helpers import *
from authlib.integrations.base_client.errors import OAuthError
from authlib.integrations.httpx_client import AsyncOAuth2Client
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)

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


    '''
    *******************************************
    ***  Getters for current machine state ****
    *******************************************
    '''

    # will return current machine mode (Brewing/StandBy)
    async def get_machine_mode(self):
        if self._lm_local_api:
            return self._lm_local_api.get_machine_mode()
        else:
            await self._update_config_obj()
            return self._config[str.upper(MACHINE_MODE)]

    async def get_coffee_boiler_enabled(self):
        if self._lm_local_api:
            return self._lm_local_api.get_coffee_boiler_enabled()
        else:
            await self._update_config_obj()
            coffee_boiler = next(item for item in self._config[str.upper(BOILERS)] if item["id"] == COFFEE_BOILER_NAME)
            return coffee_boiler["isEnabled"]

    async def get_steam_boiler_enabled(self):
        if self._lm_local_api:
            return self._lm_local_api.get_coffee_steam_enabled()
        else:
            await self._update_config_obj()
            coffee_boiler = next(item for item in self._config[str.upper(BOILERS)] if item["id"] == STEAM_BOILER_NAME)
            return coffee_boiler["isEnabled"]

    async def get_coffee_temp(self):
        if self._lm_local_api:
            return self._lm_local_api.get_coffee_temp()
        else:
            await self._update_config_obj()
            return self._config[str.upper(BOILER_TARGET_TEMP)][COFFEE_BOILER_NAME]

    async def get_steam_temp(self):
        if self._lm_local_api:
            return self._lm_local_api.get_steam_temp()
        else:
            await self._update_config_obj()
            return self._config[str.upper(BOILER_TARGET_TEMP)][STEAM_BOILER_NAME]

    async def get_plumbin_enabled(self):
        if self._lm_local_api:
            return self._lm_local_api.get_plumbin_enabled()
        else:
            await self._update_config_obj()
            return self._config[str.upper(PLUMBED_IN)]

    async def get_preinfusion_settings(self):
        if self._lm_local_api:
            return self._lm_local_api.get_preinfusion_settings(self)
        else:
            await self._update_config_obj()
            return self._config[str.upper(PRE_INFUSION_SETTINGS)]

    async def get_schedule(self):
        if self._lm_local_api:
            return self._lm_local_api.get_schedule()
        else:
            await self._update_config_obj()
            return convert_schedule(self._config[str.upper(WEEKLY_SCHEDULING_CONFIG)])

    

    '''
    *******************************************
    ***********  Functions ********************
    *******************************************
    '''

    def __init__(self):
        _logger.setLevel(logging.DEBUG)
        self._lm_local_api   = None
        self. _config        = None

    '''
    Initialize a cloud only client
    '''
    @classmethod
    async def create(cls, credentials: Credentials):
        self = cls()
        self.client = await self._connect(credentials)
        self._machine_info = await self._get_machine_info()
        self._gw_url_with_serial = GW_MACHINE_BASE_URL + "/" + self.machine_info[SERIAL_NUMBER]
        return self

    '''
    Also initialize a local API client
    '''
    @classmethod
    async def create_with_local_api(cls, credentials: Credentials, ip, port=8081):
        self = cls()
        self.client = await self._connect(credentials)
        self._machine_info = await self._get_machine_info()
        self._lm_local_api = LMLocalAPI(local_ip=ip, local_port=port, local_bearer=self.machine_info[KEY])
        self._gw_url_with_serial = GW_MACHINE_BASE_URL + "/" + self.machine_info[SERIAL_NUMBER]
        return self
        
    '''
    Establish connection by building the OAuth client and requesting the token
    '''
    async def _connect(self, credentials: Credentials):
        client = AsyncOAuth2Client(
            client_id=credentials.client_id,
            client_secret=credentials.client_secret,
            token_endpoint=TOKEN_URL
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

    '''
    update OAuth Token in client
    '''
    async def update_token(self):
        if self.client.token.is_expired():
            await self.client.refresh_token(TOKEN_URL)

    '''
    Get configuration from cloud
    '''
    async def get_config(self):
        url = f"{self._gw_url_with_serial}/configuration"
        self.update_token()
        response = await self.client.get(url)
        return self.ensure_success_response(response)

    '''
    Load the config into a variable in this class
    '''
    async def _update_config_obj(self):
        if self._config:
            # wait at least 10 seconds between config updates to not flood the remote API
            if (datetime.now() - self._last_config_update).total_seconds() < 10:
                return
        self._config = await self.get_config()
        self._last_config_update = datetime.now()

    '''
    Ensure the HTTP response code is 200
    '''
    def ensure_success_response(self, response):
        if response.is_success:
            return response.json()["data"]
        else:
            msg = f"Request to endpoint {response.url} failed with status code {response.status_code}"
            _logger.info(f"{msg}. Details: {response.text}")
            raise RequestNotSuccessful(msg)

    '''
    Get Basic machine info from the customer endpoint
    '''
    async def _get_machine_info(self):
        self.update_token()
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
            msg = "Power status can only be on or standby"
            self._logger.debug(msg)
            raise ValueError(msg)
        else:
            data = {"status": power_status}
            url = f"{self._gw_url_with_serial}/status"
            self.update_token()
            response = await self.client.post(url, json=data)
            return self.ensure_success_response(response)

    '''
    Turn Steamboiler on or off
    '''
    async def set_steam(self, steam_state:bool):
        if not type(steam_state) == bool:
            msg = "Steam state must be boolean"
            _logger.debug(msg)
            raise TypeError(msg)
        else:
            data = {"identifier": STEAM_BOILER_NAME, "state": steam_state}
            url = f"{self._gw_url_with_serial}/enable-boiler"
            self.update_token()
            response = await self.client.post(url, json=data)
            return self.ensure_success_response(response)

    '''
    Set steamboiler temperature (in Celsius)
    '''
    async def set_steam_temp(self, temperature:int):
        if not type(temperature) == int:
            msg = "Steam temp must be integer"
            _logger.debug(msg)
            raise TypeError(msg)
        elif not temperature == 131 and not temperature == 128 and not temperature == 126:
            msg = "Steam temp must be one of 126, 128, 131 (°C)"
            _logger.debug(msg)
            raise ValueError(msg)
        else:
            data = { "identifier": STEAM_BOILER_NAME, "value": temperature}
            url = f"{self._gw_url_with_serial}/target-boiler"
            self.update_token()
            response = await self.client.post(url, json=data)
            return self.ensure_success_response(response)

    '''
    Set coffee boiler temperature (in Celsius)
    '''
    async def set_coffee_temp(self, temperature:int):

        if temperature > 104 or temperature < 85:
            msg = "Coffee temp must be between 85 and 104 (°C)"
            _logger.debug(msg)
            raise ValueError(msg)
        else:
            temperature = round(temperature, 1)
            data = { "identifier": COFFEE_BOILER_NAME, "value": temperature}
            url = f"{self._gw_url_with_serial}/target-boiler"
            self.update_token()
            response = await self.client.post(url, json=data)
            return self.ensure_success_response(response)

    '''
    Enable/Disable Pre-Brew or Pre-Infusion (mutually exclusive)
    '''
    async def _set_pre_brew_infusion(self, mode):
        if mode != "Disabled" and mode != "TypeB" and mode != "Enabled":
            msg = "Pre-Infusion/Pre-Brew can only be TypeB (PreInfusion), Enabled (Pre-Brew) or Disabled"
            _logger.debug(msg)
            raise ValueError(msg)
        elif mode == "TypedB" and not (await self.get_plumbin_enabled()):
            msg = "Pre-Infusion can only be enabled when plumbin is enabled"
            _logger.debug(msg)
            raise ValueError(msg)
        else:
            url = f"{self._gw_url_with_serial}/enable-preinfusion"
            data = {"mode": mode}
            self.update_token()
            response = await self.client.post(url, json=data)
            return self.ensure_success_response(response)

    '''
    Enable/Disable Pre-brew (Mode = Enabled)
    '''
    async def set_prebrew(self, mode):
        return await self._set_pre_brew_infusion(mode)

    '''
    Enable/Disable Pre-Infusion (Mode = TypeB)
    '''
    async def set_preinfusion(self, mode):
        return await self._set_pre_brew_infusion(mode)

    '''
    Set Pre-Brew details
    '''
    async def configure_prebrew(self, prebrewOnTime=5000, prebrewOffTime=5000):
        if type(prebrewOnTime) != int or type(prebrewOffTime) != int:
            msg = "Prebrew times must be in ms (integer)"
            _logger.debug(msg)
            raise TypeError(msg)
        else:
            if prebrewOnTime % 100 != 0 or prebrewOffTime % 100 != 0:
                msg = "Prebrew times must be multiple of 100"
                _logger.debug(msg)
                raise ValueError(msg)
            url = f"{self._gw_url_with_serial}/setting-preinfusion"
            data = {
                "button": "Continuous",
                "group": "Group1",
                "holdTimeMs": prebrewOffTime,
                "wetTimeMs": prebrewOnTime
            }
            self.update_token()
            response = await self.client.post(url, json=data)
            return self.ensure_success_response(response)

    '''
    Enable or disable plumbin mode
    '''
    async def enable_plumbin(self, enable:bool):
        if not type(enable) == bool:
            msg = "Enable param must be boolean"
            _logger.debug(msg)
            raise TypeError(msg)
        else:
            data = {"enable": enable}
            url = f"{self._gw_url_with_serial}/enable-plumbin"
            self.update_token()
            response = await self.client.post(url, json=data)
            return self.ensure_success_response(response)

    '''
    Set auto-on/off schedule


    schedule object:
    [
        {
            "day": "MONDAY",
            "enable": false,
            "off": "00:00",
            "on": "00:00"
        },
        {
            "day": "TUESDAY",
            "enable": false,
            "off": "00:00",
            "on": "00:00"
        },
        {
            "day": "WEDNESDAY",
            "enable": false,
            "off": "00:00",
            "on": "00:00"
        },
        {
            "day": "THURSDAY",
            "enable": false,
            "off": "00:00",
            "on": "00:00"
        },
        {
            "day": "FRIDAY",
            "enable": false,
            "off": "00:00",
            "on": "00:00"
        },
        {
            "day": "SATURDAY",
            "enable": false,
            "off": "00:00",
            "on": "00:00"
        },
        {
            "day": "SUNDAY",
            "enable": false,
            "off": "00:00",
            "on": "00:00"
        }
    ]
    '''
    async def configure_schedule(self, enable: bool, schedule: list):
        url = f"{self._gw_url_with_serial}/scheduling"
        data = {"enable": enable, "days": schedule}
        self.update_token()
        response = await self.client.post(url, json=data)
        return self.ensure_success_response(response)