from .const import *
from .exceptions import *
from .lmlocalapi import LMLocalAPI
from .helpers import *
from authlib.integrations.base_client.errors import OAuthError
from authlib.integrations.httpx_client import AsyncOAuth2Client
from requests.exceptions import RequestException
from datetime import datetime
import logging
import asyncio

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

    @property
    def model_name(self):
        return self._machine_info[MODEL_NAME]
    
    @property 
    def firmware_version(self):
        return self._firmware["machine_firmware"]["version"]

    @property
    def config(self):
        """ Return the config with capitalized keys to be consistent across local/remote APIs """
        return {k.upper():v for k,v in self._config.items()}
    
    @property
    def status(self):
        return self._status
    
    @property
    def statistics(self):
        return self._statistics
    
    @property 
    def current_status(self):
        """ Build object which holds status for lamarzocco Home Assistant Integration"""
        return {
            "power": True if self.config[MACHINE_MODE] == "BrewingMode" else False,
            "enable_prebrewing": True if self.config[PRE_INFUSION_SETTINGS]["mode"] == "Enabled" else False,
            "enable_preinfusion": True if self.config[PRE_INFUSION_SETTINGS]["mode"] == "TypeB" else False,
            "steam_boiler_enable": next(item for item in self.config[BOILERS] if item["id"] == STEAM_BOILER_NAME)["isEnabled"],
            "global_auto": self.config[WEEKLY_SCHEDULING_CONFIG]["enabled"],
            "coffee_temp": self.status[COFFEE_TEMP],
            "coffee_set_temp": self.config[BOILER_TARGET_TEMP][COFFEE_BOILER_NAME],
            "steam_temp": self.status[STEAM_TEMP],
            "steam_set_temp": self.config[BOILER_TARGET_TEMP][STEAM_BOILER_NAME],
            "water_reservoir_contact": self.status[TANK_LEVEL],
            "plumbin_enable": self.config[PLUMBED_IN],
            "drinks_k1":        self.statistics[0]["count"],
            "drinks_k2":        self.statistics[1]["count"],
            "drinks_k3":        self.statistics[2]["count"],
            "drinks_k4":        self.statistics[3]["count"],
            "continuous":       self.statistics[4]["count"],
            "total_flushing":   self.statistics[5]["count"],
            "active_brew": self.status[ACTIVE_BREW] if self._lm_local_api else False
        }


    '''
    *******************************************
    ***  Getters for current machine state ****
    *******************************************
    '''

    # will return current machine mode (Brewing/StandBy)
    async def get_machine_mode(self):
        await self.update_local_machine_status()
        return self.config[MACHINE_MODE]

    async def get_coffee_boiler_enabled(self):
        await self.update_local_machine_status()
        coffee_boiler = next(item for item in self.config[BOILERS] if item["id"] == COFFEE_BOILER_NAME)
        return coffee_boiler["isEnabled"]

    async def get_steam_boiler_enabled(self):
        await self.update_local_machine_status()
        coffee_boiler = next(item for item in self.config[BOILERS] if item["id"] == STEAM_BOILER_NAME)
        return coffee_boiler["isEnabled"]

    async def get_coffee_temp(self):
        await self.update_local_machine_status()
        return self.config[BOILER_TARGET_TEMP][COFFEE_BOILER_NAME]

    async def get_steam_temp(self):
        await self.update_local_machine_status()
        return self.config[BOILER_TARGET_TEMP][STEAM_BOILER_NAME]

    async def get_plumbin_enabled(self):
        await self.update_local_machine_status()
        return self.config[PLUMBED_IN]

    async def get_preinfusion_settings(self):
        await self.update_local_machine_status()
        return self.config[PRE_INFUSION_SETTINGS]

    async def get_schedule(self):
        await self.update_local_machine_status()
        return schedule_out_to_in(self.config[WEEKLY_SCHEDULING_CONFIG])
    

    '''
    *******************************************
    ***********  Functions ********************
    *******************************************
    '''

    def __init__(self):
        _logger.setLevel(logging.DEBUG)
        self._lm_local_api      = None
        self. _config           = {}
        self. _status           = {}
        self. _statistics       = {}

    '''
    Initialize a cloud only client
    '''
    @classmethod
    async def create(cls, credentials):
        self = cls()
        self.client = await self._connect(credentials)
        self._machine_info = await self._get_machine_info()
        self._gw_url_with_serial = GW_MACHINE_BASE_URL + "/" + self.machine_info[SERIAL_NUMBER]
        self._firmware = await self.get_firmware()
        await self.update_local_machine_status()
        return self

    '''
    Also initialize a local API client
    '''
    @classmethod
    async def create_with_local_api(cls, credentials, ip, port=8081):
        self = cls()
        self.client = await self._connect(credentials)
        self._machine_info = await self._get_machine_info()
        self._lm_local_api = LMLocalAPI(local_ip=ip, local_port=port, local_bearer=self.machine_info[KEY])
        self._gw_url_with_serial = GW_MACHINE_BASE_URL + "/" + self.machine_info[SERIAL_NUMBER]
        self._firmware = await self.get_firmware()
        asyncio.create_task(self._lm_local_api.websocket_connect())
        await self.update_local_machine_status(in_init=True)
        return self
        
    '''
    Establish connection by building the OAuth client and requesting the token
    '''
    async def _connect(self, credentials):
        client = AsyncOAuth2Client(
            client_id=credentials["client_id"],
            client_secret=credentials["client_secret"],
            token_endpoint=TOKEN_URL
        )

        headers = {
            "client_id": credentials["client_id"],
            "client_secret": credentials["client_secret"],
        }

        try:
            await client.fetch_token(
                url=TOKEN_URL,
                username=credentials["username"],
                password=credentials["password"],
                headers=headers,
            )
            return client
    
        except OAuthError as err:
            raise AuthFail("Authorization failure") from err
        

    '''
    Get configuration from cloud
    '''
    async def get_config(self):
        url = f"{self._gw_url_with_serial}/configuration"
        try:
            config = await self._rest_api_call(url=url, verb="GET")
            return config
        except Exception as e:
            _logger.error(f"Could not get config from cloud. Full error: {e}")
            return self._config
        
    '''
    Load the config into variables in this class
    '''
    async def _update_config_obj(self, force_update=False):
        if self._config:
            # wait at least 10 seconds between config updates to not flood the remote API
            if (datetime.now() - self._last_config_update).total_seconds() < POLLING_DELAY_S or force_update:
                return
        self._config = await self.get_config()
        self._last_config_update = datetime.now()

    '''
    Get status from cloud
    '''
    async def get_status(self):
        url = f"{self._gw_url_with_serial}/status"
        try:
            status = await self._rest_api_call(url=url, verb="GET")
            return status
        except Exception as e:
            _logger.error(f"Could not get config from cloud. Full error: {e}")
            return self._status
        
    async def _update_status_obj(self, force_update=False):
        if self._status:
            # wait at least 10 seconds between config updates to not flood the remote API
            if (datetime.now() - self._last_status_update).total_seconds() < POLLING_DELAY_S or force_update:
                return
        self._status = await self.get_status()
        self._last_status_update = datetime.now() 

    '''
    update config object
    '''
    async def update_local_machine_status(self, in_init=False):
        if self._lm_local_api:
            try:
                conf = await self._lm_local_api.local_get_config()
                self._config = {k.upper():v for k,v in conf.items()}
            except RequestException as e:
                _logger.warn(f"Could not connect to local API although initialized. Full error: {e}")
                await self._update_config_obj()

            if self._lm_local_api._timestamp_last_websocket_msg == None or (datetime.now() - self._lm_local_api._timestamp_last_websocket_msg).total_seconds() > 30: 
                if not in_init: # during init we don't want to log this warning
                    _logger.warn("Could not get local machine status. Falling back to cloud status.")
                await self._update_status_obj()
                self._status[ACTIVE_BREW] = False
            else:
                # Get local status from WebSockets
                print("Using local status")
                self._status = self._lm_local_api._status # reference to the same object tp get websocket updates
        else:
            await self._update_config_obj()     
            await self._update_status_obj()

        await self._update_statistics_obj()

    '''
    Get statistics
    '''
    async def get_statistics(self):
        url = f"{self._gw_url_with_serial}/statistics/counters"
        try:
            statistics = await self._rest_api_call(url=url, verb="GET")
            return statistics
        except Exception as e:
            _logger.error(f"Could not get config from cloud. Full error: {e}")
            return self._statistics   


    async def _update_statistics_obj(self, force_update=False):
        if self._statistics:
            # wait at least 10 seconds between config updates to not flood the remote API
            if (datetime.now() - self._last_statistics_update).total_seconds() < POLLING_DELAY_STATISTICS_S or force_update:
                return
        self._statistics = await self.get_statistics()
        self._last_statistics_update = datetime.now() 


    '''
    Wrapper for the API call
    '''
    async def _rest_api_call(self, url, verb="GET", data=None):
        # make sure oauth token is still valid
        if self.client.token.is_expired():
            await self.client.refresh_token(TOKEN_URL)

        # make API call
        if verb == "GET":
            response = await self.client.get(url)
        elif verb == "POST":
            response = await self.client.post(url, json=data)
        else:
            raise NotImplemented(f"Wrapper function for Verb {verb} not implemented yet!")
        
        # ensure status code indicates success
        if response.is_success:
            return response.json()["data"]
        else:
            msg = f"Request to endpoint {response.url} failed with status code {response.status_code}"
            _logger.warn(f"{msg}. Details: {response.text}")
            raise RequestNotSuccessful(msg)
        

    '''
    Get Basic machine info from the customer endpoint
    '''
    async def _get_machine_info(self):
        data = await self._rest_api_call(url=CUSTOMER_URL, verb="GET")

        machine_info = {}
        fleet = data["fleet"][0]
        machine_info[KEY] = fleet["communicationKey"]
        machine_info[SERIAL_NUMBER] = fleet["machine"]["serialNumber"]
        machine_info[MACHINE_NAME] = fleet["name"]
        machine_info[MODEL_NAME] = fleet["machine"]["model"]["name"]
        return machine_info
    
    '''
    Get Firmware details
    '''
    async def get_firmware(self):
        url = f"{self._gw_url_with_serial}/firmwarev2/"
        return await self._rest_api_call(url=url, verb="GET")


    '''
    Machine power wrapper with bool input
    '''
    async def set_power(self, enabled: bool):
        power_status = "ON" if enabled else "STANDBY"
        return await self._set_power(power_status)

    '''
    Turn power of machine on or off
    '''
    async def _set_power(self, power_status: str):
        power_status = str.upper(power_status)
        if not power_status in ["ON", "STANDBY"]:
            msg = "Power status can only be on or standby"
            self._logger.debug(msg)
            raise ValueError(msg)
        else:
            data = {"status": power_status}
            url = f"{self._gw_url_with_serial}/status"
            response = await self._rest_api_call(url=url, verb="POST", data=data)
            self._config[MACHINE_MODE] = "BrewingMode" if power_status == "ON" else "StandBy"
            return response

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
            response = await self._rest_api_call(url=url, verb="POST", data=data)
            idx = [STEAM_BOILER_NAME in i['id'] for i in self.config[BOILERS]].index(True)
            self._config[BOILERS][idx]["isEnabled"] = steam_state
            return response

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
            response = await self._rest_api_call(url=url, verb="POST", data=data)
            self._config[BOILER_TARGET_TEMP][STEAM_BOILER_NAME] = temperature
            return response

    '''
    Set coffee boiler temperature (in Celsius)
    '''
    async def set_coffee_temp(self, temperature):

        if temperature > 104 or temperature < 85:
            msg = "Coffee temp must be between 85 and 104 (°C)"
            _logger.debug(msg)
            raise ValueError(msg)
        else:
            temperature = round(temperature, 1)
            data = { "identifier": COFFEE_BOILER_NAME, "value": temperature}
            url = f"{self._gw_url_with_serial}/target-boiler"
            response = await self._rest_api_call(url=url, verb="POST", data=data)
            self._config[BOILER_TARGET_TEMP][COFFEE_BOILER_NAME] = temperature
            return response

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
            response = await self._rest_api_call(url=url, verb="POST", data=data)
            self._config[PRE_INFUSION_SETTINGS]["mode"] = mode
            return response

    '''
    Enable/Disable Pre-brew (Mode = Enabled)
    '''
    async def set_prebrew(self, enabled: bool):
        mode = "Enabled" if enabled else "Disabled"
        return await self._set_pre_brew_infusion(mode)

    '''
    Enable/Disable Pre-Infusion (Mode = TypeB)
    '''
    async def set_preinfusion(self, enabled: bool):
        mode = "TypeB" if enabled else "Disabled"
        return await self._set_pre_brew_infusion(mode)

    '''
    Set Pre-Brew details
    Also used for preinfusion (prebrewOnTime=0, prebrewOnTime=ms)
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
            response = await self._rest_api_call(url=url, verb="POST", data=data)

            self._config[PRE_INFUSION_SETTINGS]["Group1"][0]["preWetTime"] = prebrewOnTime % 1000
            self._config[PRE_INFUSION_SETTINGS]["Group1"][0]["preWetHoldTime"] = prebrewOffTime % 1000
            return response

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
            response = await self._rest_api_call(url=url, verb="POST", data=data)
            self._config[PLUMBED_IN] = enable
            return response

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
        response = await self._rest_api_call(url=url, verb="POST", data=data)
        self._config[WEEKLY_SCHEDULING_CONFIG] = schedule_in_to_out(enable, schedule)
        return response

    async def set_auto_on_off(self, day_of_week, hour_on, minute_on, hour_off, minute_off):
        schedule = await self.get_schedule()
        idx = [index for (index, d) in enumerate(schedule) if d["day"] == day_of_week.upper()][0]
        schedule[idx]["enable"] = True
        schedule[idx]["on"] = f"{hour_on:02d}:{minute_on:02d}"
        schedule[idx]["off"] = f"{hour_off:02d}:{minute_off:02d}"
        return await self.configure_schedule(self.config[WEEKLY_SCHEDULING_CONFIG]["enabled"], schedule)
    
    async def set_auto_on_off_enable(self, day_of_week, enable):
        schedule = await self.get_schedule()
        idx = [index for (index, d) in enumerate(schedule) if d["day"] == day_of_week.upper()][0]
        schedule[idx]["enable"] = enable
        return await self.configure_schedule(self.config[WEEKLY_SCHEDULING_CONFIG]["enabled"], schedule)


    '''
    Send command to start backflushing
    '''
    async def start_backflush(self):
        url = f"{self._gw_url_with_serial}/enable-backflush"
        data = {"enable": True}
        response = await self._rest_api_call(url=url, verb="POST", data=data)
        self._config[BACKFLUSH_ENABLED] = True
        return response