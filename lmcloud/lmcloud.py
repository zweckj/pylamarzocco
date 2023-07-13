from .const import *
from .exceptions import *
from .lmlocalapi import LMLocalAPI
from .lmbluetooth import LMBluetooth
from .helpers import *
from authlib.integrations.base_client.errors import OAuthError
from authlib.integrations.httpx_client import AsyncOAuth2Client
from datetime import datetime
from bleak import BleakError
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
    def model_name(self) -> str:
        return self._machine_info[MODEL_NAME]
    
    @property 
    def firmware_version(self) -> str:
        return self._firmware["machine_firmware"]["version"]
    
    @property
    def latest_firmware_version(self) -> str:
        return self._firmware["machine_firmware"]["targetVersion"]
    
    @property
    def date_received(self):
        return self._date_received

    @property
    def config(self):
        """ 
        Return the config with capitalized keys to be consistent across local/remote APIs 
        """
        return self._config
    
    @property
    def power(self) -> bool:
        return True if self.config[MACHINE_MODE] == "BrewingMode" else False
    
    @property 
    def steam_boiler_enabled(self) -> bool:
        return self._config_steamboiler["isEnabled"]
    
    @property
    def is_heating(self) -> bool:
        coffee_heating = (float(self._config_coffeeboiler["current"]) < float(self._config_coffeeboiler["target"])) \
            and self.power 
        steam_heating = float(self._config_steamboiler["current"]) < float(self._config_steamboiler["target"]) \
            and self.power and self.steam_boiler_enabled
        return coffee_heating or steam_heating

    @property
    def brew_active(self) -> str:
        return self._brew_active
    
    @property 
    def heating_state(self) -> list:
        return [
            "heating_on" if self.power else "heating_off",
            "steam_heater_on" if self.steam_boiler_enabled else "steam_heater_off"
        ]

    @property
    def status(self):
        return self._status
    
    @property
    def statistics(self):
        return self._statistics

    @property
    def schedule(self):
        return schedule_out_to_in(self.config[WEEKLY_SCHEDULING_CONFIG])
    
    @property 
    def current_status(self) -> dict:
        # extend the current status from super with active brew property
        self._current_status[BREW_ACTIVE] = self.brew_active
        return self._current_status
    

    '''
    *******************************************
    ***********  Functions ********************
    *******************************************
    '''

    def __init__(self):
        _logger.setLevel(logging.DEBUG)
        self._lm_local_api         = None
        self._lm_bluetooth         = None
        self. _config              = {}
        self. _status              = {}
        self._current_status       = {}
        self. _config_steamboiler  = {}
        self. _config_coffeeboiler = {}
        self. _statistics          = {}
        self._use_websocket        = False
        self._brew_active          = False


    @classmethod
    async def create(cls, credentials):
        '''
        Initialize a cloud only client
        '''
        self = cls()
        self.client = await self._connect(credentials)
        self._machine_info = await self._get_machine_info()
        self._gw_url_with_serial = GW_MACHINE_BASE_URL + "/" + self.machine_info[SERIAL_NUMBER]
        self._firmware = await self.get_firmware()
        await self.update_local_machine_status()
        return self


    @classmethod
    async def create_with_local_api(cls, credentials, ip, port=8081, use_websocket=False, use_bluetooth=False, bluetooth_scanner=None):
        '''
        Also initialize a local API client
        '''
        self = cls()
        await self.init_with_local_api(credentials, ip, port, use_websocket, use_bluetooth, bluetooth_scanner)

        await self.update_local_machine_status(in_init=True)
        return self
    

    async def init_with_local_api(self, credentials, ip, port=8081, use_websocket=False, use_bluetooth=False, bluetooth_scanner=None):
        ''' init where data is loaded '''
        self.client = await self._connect(credentials)
        self._machine_info = await self._get_machine_info()
        self._lm_local_api = LMLocalAPI(local_ip=ip, local_port=port, local_bearer=self.machine_info[KEY])
        self._gw_url_with_serial = GW_MACHINE_BASE_URL + "/" + self.machine_info[SERIAL_NUMBER]
        self._firmware = await self.get_firmware()
        self._date_received = datetime.now()

        # init websockets if set
        if use_websocket:
            self._use_websocket = True
            asyncio.create_task(self._lm_local_api.websocket_connect())

        # init bluetooth if set
        if use_bluetooth:
            try:
                self._lm_bluetooth = await LMBluetooth.create(username=credentials["username"], 
                                                        serial_number=self.machine_info[SERIAL_NUMBER],
                                                        token=self.machine_info[KEY],
                                                        bleak_scanner=bluetooth_scanner)
            except BluetoothDeviceNotFound as e:
                _logger.warn(f"Could not find bluetooth device. Bluetooth commands will not be available and commands will all be sent through cloud.")
                _logger.debug(f"Full error: {e}")
            except BleakError as e:
                _logger.warn(f"Bleak encountered an error while trying to connect to bluetooth device. \
                             Maybe no bluetooth adapter is available? Bluetooth commands will not be available and commands will all be sent through cloud.")
                _logger.debug(f"Full error: {e}")
        

    async def _connect(self, credentials):
        '''
        Establish connection by building the OAuth client and requesting the token
        '''

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
        

    async def get_config(self):
        '''
        Get configuration from cloud
        '''
        
        url = f"{self._gw_url_with_serial}/configuration"
        try:
            config = await self._rest_api_call(url=url, verb="GET")
            return config
        except Exception as e:
            _logger.error(f"Could not get config from cloud. Full error: {e}")
            return self._config
        

    async def _update_config_obj(self, force_update=False):
        '''
        Load the config into variables in this class
        '''

        if self._config:
            # wait at least 10 seconds between config updates to not flood the remote API
            if (datetime.now() - self._last_config_update).total_seconds() < POLLING_DELAY_S or force_update:
                return
        self._config = await self.get_config()
        self._last_config_update = datetime.now()


    async def update_local_machine_status(self, in_init=False):
        '''
        update config object
        '''

        if self._lm_local_api:
            try:
                self._config = await self._lm_local_api.local_get_config()
            except Exception as e:
                _logger.warn(f"Could not connect to local API although initialized. Full error: {e}")
                await self._update_config_obj()

            if self._lm_local_api._timestamp_last_websocket_msg == None or (datetime.now() - self._lm_local_api._timestamp_last_websocket_msg).total_seconds() > 30: 
                if self._use_websocket and not in_init:  # during init we don't want to log this warning
                    _logger.warn("Could not get local machine status. Falling back to cloud status.")
            else:
                # Get local status from WebSockets
                _logger.debug("Using local status object")
                self._status = self._lm_local_api._status  # reference to the same object tp get websocket updates
        else:
            await self._update_config_obj() 

        self._config_coffeeboiler = next(item for item in self.config[BOILERS] if item["id"] == COFFEE_BOILER_NAME)
        self._config_steamboiler  = next(item for item in self.config[BOILERS] if item["id"] == STEAM_BOILER_NAME)


        await self._update_statistics_obj()
        self._date_received = datetime.now()
        self._current_status = self._build_current_status()


    async def get_statistics(self):
        '''
        Get statistics
        '''

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



    async def _rest_api_call(self, url, verb="GET", data=None):
        '''
        Wrapper for the API call
        '''

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
        

    async def _send_bluetooth_command(self, func, param):
        '''
        Wrapper for bluetooth commands
        '''
        try:
            await func(param)
            return True
        except BleakError as e:
            _logger.warn("Could not send command to bluetooth device, even though initalized. Falling back to cloud...")
            _logger.debug(f"Full error: {e}")
            return False
        

    async def _get_machine_info(self):
        '''
        Get Basic machine info from the customer endpoint
        '''

        data = await self._rest_api_call(url=CUSTOMER_URL, verb="GET")

        machine_info = {}
        fleet = data["fleet"][0]
        machine_info[KEY] = fleet["communicationKey"]
        machine_info[SERIAL_NUMBER] = fleet["machine"]["serialNumber"]
        machine_info[MACHINE_NAME] = fleet["name"]
        machine_info[MODEL_NAME] = fleet["machine"]["model"]["name"]
        return machine_info
    

    async def get_firmware(self):
        '''
        Get Firmware details
        '''

        url = f"{self._gw_url_with_serial}/firmware/"
        return await self._rest_api_call(url=url, verb="GET")

   
    async def set_power(self, enabled: bool):
        '''
        Turn power of machine on or off
        '''

        if self._lm_bluetooth:
            bt_ok = await self._send_bluetooth_command(self._lm_bluetooth.set_power, enabled)
            response = "Ok"

        mode = "BrewingMode" if enabled else "StandBy"

        if not self._lm_bluetooth or not bt_ok:
            data = {"status": mode}
            url = f"{self._gw_url_with_serial}/status"
            response = await self._rest_api_call(url=url, verb="POST", data=data)

        self._config[MACHINE_MODE] = mode
        return response


    async def set_steam(self, steam_state:bool):
        '''
        Turn Steamboiler on or off
        '''

        if not type(steam_state) == bool:
            msg = "Steam state must be boolean"
            _logger.debug(msg)
            raise TypeError(msg)
        else:
            if self._lm_bluetooth:
                bt_ok = await self._send_bluetooth_command(self._lm_bluetooth.set_steam, steam_state)
                response = "Ok"

            if not self._lm_bluetooth or not bt_ok:
                data = {"identifier": STEAM_BOILER_NAME, "state": steam_state}
                url = f"{self._gw_url_with_serial}/enable-boiler"
                response = await self._rest_api_call(url=url, verb="POST", data=data)
            
            idx = [STEAM_BOILER_NAME in i['id'] for i in self.config[BOILERS]].index(True)
            self._config[BOILERS][idx]["isEnabled"] = steam_state
            return response


    async def set_steam_temp(self, temperature:int):
        '''
        Set steamboiler temperature (in Celsius)
        '''

        if not type(temperature) == int:
            msg = "Steam temp must be integer"
            _logger.debug(msg)
            raise TypeError(msg)
        
        elif not temperature == 131 and not temperature == 128 and not temperature == 126:
            msg = "Steam temp must be one of 126, 128, 131 (°C)"
            _logger.debug(msg)
            raise ValueError(msg)
        
        else:
            if self._lm_bluetooth:
                bt_ok = await self._send_bluetooth_command(self._lm_bluetooth.set_steam_temp, temperature)
                response = "Ok"
                    
            if not self._lm_bluetooth or not bt_ok:
                data = { "identifier": STEAM_BOILER_NAME, "value": temperature}
                url = f"{self._gw_url_with_serial}/target-boiler"
                response = await self._rest_api_call(url=url, verb="POST", data=data)

            self._config[BOILER_TARGET_TEMP][STEAM_BOILER_NAME] = temperature
            return response


    async def set_coffee_temp(self, temperature):
        '''
        Set coffee boiler temperature (in Celsius)
        '''

        if temperature > 104 or temperature < 85:
            msg = "Coffee temp must be between 85 and 104 (°C)"
            _logger.debug(msg)
            raise ValueError(msg)
        else: 
            temperature = round(temperature, 1)

            if self._lm_bluetooth:
                bt_ok = await self._send_bluetooth_command(self._lm_bluetooth.set_coffee_temp, temperature)
                response = "Ok"
            
            if not self._lm_bluetooth or not bt_ok:
                data = { "identifier": COFFEE_BOILER_NAME, "value": temperature}
                url = f"{self._gw_url_with_serial}/target-boiler"
                response = await self._rest_api_call(url=url, verb="POST", data=data)

            self._config[BOILER_TARGET_TEMP][COFFEE_BOILER_NAME] = temperature
            return response


    async def _set_pre_brew_infusion(self, mode):
        '''
        Enable/Disable Pre-Brew or Pre-Infusion (mutually exclusive)
        '''

        if mode != "Disabled" and mode != "TypeB" and mode != "Enabled":
            msg = "Pre-Infusion/Pre-Brew can only be TypeB (PreInfusion), Enabled (Pre-Brew) or Disabled"
            _logger.debug(msg)
            raise ValueError(msg)
        elif mode == "TypedB" and not self.config[PLUMBED_IN]:
            msg = "Pre-Infusion can only be enabled when plumbin is enabled"
            _logger.debug(msg)
            raise ValueError(msg)
        else:
            url = f"{self._gw_url_with_serial}/enable-preinfusion"
            data = {"mode": mode}
            response = await self._rest_api_call(url=url, verb="POST", data=data)
            self._config[PRE_INFUSION_SETTINGS]["mode"] = mode
            return response

    async def set_prebrew(self, enabled: bool):
        '''
        Enable/Disable Pre-brew (Mode = Enabled)
        '''

        mode = "Enabled" if enabled else "Disabled"
        return await self._set_pre_brew_infusion(mode)


    async def set_preinfusion(self, enabled: bool):
        '''
        Enable/Disable Pre-Infusion (Mode = TypeB)
        '''

        mode = "TypeB" if enabled else "Disabled"
        return await self._set_pre_brew_infusion(mode)


    async def configure_prebrew(self, prebrewOnTime=5000, prebrewOffTime=5000):
        '''
        Set Pre-Brew details
        Also used for preinfusion (prebrewOnTime=0, prebrewOnTime=ms)
        '''

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
                "button": "DoseA",
                "group": "Group1",
                "holdTimeMs": prebrewOffTime,
                "wetTimeMs": prebrewOnTime
            }
            response = await self._rest_api_call(url=url, verb="POST", data=data)

            self._config[PRE_INFUSION_SETTINGS]["Group1"][0]["preWetTime"] = prebrewOnTime % 1000
            self._config[PRE_INFUSION_SETTINGS]["Group1"][0]["preWetHoldTime"] = prebrewOffTime % 1000
            return response


    async def enable_plumbin(self, enable: bool):
        '''
        Enable or disable plumbin mode
        '''

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
        
    async def set_dose(self, key: int, value: int): 
        """Set the value for a dose"""

        if key < 1 or key > 4:
            msg = f"Key must be an integer value between 1 and 4, was {key}"
            _logger.debug(msg)
            raise ValueError(msg)
        
        dose_index = f"Dose{chr(key + 64)}"
        
        url = f"{self._gw_url_with_serial}/dose"
        data = {
                "doseIndex": dose_index,
                "doseType": "PulsesType",
                "groupNumber": "Group1",
                "stopTarget": value
            }
        
        response = await self._rest_api_call(url=url, verb="POST", data=data)   
        idx = next(index for index, dose in enumerate(data["groupCapabilities"][0]["doses"]) if dose["doseIndex"] == dose_index)
        self._config["groupCapabilities"][0]["doses"][idx]["stopTarget"] = value
        return response
    

    async def set_dose_hot_water(self, value: int):
        """Set the value for the hot water dose"""
        url = f"{self._gw_url_with_serial}/dose-tea"
        data = {"dose_index": "DoseA", "value": value}
        response = await self._rest_api_call(url=url, verb="POST", data=data)
        self._config["teaDoses"]["DoseA"]["stopTarget"] = value
        return response
    

    async def configure_schedule(self, enable: bool, schedule: list):
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

        url = f"{self._gw_url_with_serial}/scheduling"
        data = {"enable": enable, "days": schedule}
        response = await self._rest_api_call(url=url, verb="POST", data=data)
        self._config[WEEKLY_SCHEDULING_CONFIG] = schedule_in_to_out(enable, schedule)
        return response


    async def set_auto_on_off(self, day_of_week, hour_on, minute_on, hour_off, minute_off):
        schedule = self.schedule
        idx = [index for (index, d) in enumerate(schedule) if d["day"] == day_of_week.upper()][0]
        schedule[idx]["enable"] = True
        schedule[idx]["on"] = f"{hour_on:02d}:{minute_on:02d}"
        schedule[idx]["off"] = f"{hour_off:02d}:{minute_off:02d}"
        return await self.configure_schedule(self.config[WEEKLY_SCHEDULING_CONFIG]["enabled"], schedule)
    

    async def set_auto_on_off_enable(self, day_of_week, enable):
        schedule = self.schedule
        idx = [index for (index, d) in enumerate(schedule) if d["day"] == day_of_week.upper()][0]
        schedule[idx]["enable"] = enable
        return await self.configure_schedule(self.config[WEEKLY_SCHEDULING_CONFIG]["enabled"], schedule)
    


    async def start_backflush(self):
        '''
        Send command to start backflushing
        '''

        url = f"{self._gw_url_with_serial}/enable-backflush"
        data = {"enable": True}
        response = await self._rest_api_call(url=url, verb="POST", data=data)
        self._config[BACKFLUSH_ENABLED] = True
        return response

    def _build_current_status(self):
        """ 
        Build object which holds status for lamarzocco Home Assistant Integration
        """

        state = {
            "power":                        self.power,
            "enable_prebrewing":            True if self.config[PRE_INFUSION_SETTINGS]["mode"] == "Enabled" else False,
            "enable_preinfusion":           True if self.config[PRE_INFUSION_SETTINGS]["mode"] == "TypeB" else False,
            "steam_boiler_enable":          self.steam_boiler_enabled,
            "global_auto":                  self.config[WEEKLY_SCHEDULING_CONFIG]["enabled"],
            "coffee_temp":                  self._config_coffeeboiler[CURRENT],
            "coffee_set_temp":              self._config_coffeeboiler[TARGET],
            "steam_temp":                   self._config_steamboiler[CURRENT],
            "steam_set_temp":               self._config_steamboiler[TARGET],
            "water_reservoir_contact":      self.config[TANK_STATUS],
            "plumbin_enable":               self.config[PLUMBED_IN],
            "date_received:":               self.date_received,
            "machine_name":                 self.machine_info[MACHINE_NAME],
            "model_name":                   self.machine_info[MODEL_NAME],
            "update_available":             self.firmware_version != self.latest_firmware_version,
            "heating_state":                self.heating_state,
        }

        doses = parse_doses(self.config)
        preinfusion_settings = parse_preinfusion_settings(self.config)
        schedule = schedule_out_to_hass(self.config)
        statistics = parse_statistics(self.statistics)
        return state | doses | preinfusion_settings | schedule | statistics
