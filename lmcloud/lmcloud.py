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
    def machine_info(self) -> dict:
        return self._machine_info

    @property
    def model_name(self) -> str:
        return self._machine_info[MODEL_NAME]

    @property
    def serial_number(self) -> str:
        return self.machine_info[SERIAL_NUMBER]
    
    @property 
    def firmware_version(self) -> str:
        return self._firmware.get("machine_firmware", {}).get("version")
    
    @property
    def latest_firmware_version(self) -> str:
        return self._firmware.get("machine_firmware", {}).get("targetVersion")
    
    @property
    def gateway_version(self) -> str:
        return self._firmware.get("gateway_firmware", {}).get("version")

    @property
    def latest_gateway_version(self) -> str:
        return self._firmware.get("gateway_firmware", {}).get("targetVersion")
    
    @property
    def date_received(self):
        return self._date_received
    
    @property
    def websocket_terminating(self):
        if self._lm_local_api:
            return self._lm_local_api.terminating
        return False
    
    @websocket_terminating.setter
    def websocket_terminating(self, value):
        if self._lm_local_api:
            self._lm_local_api.terminating = value

    @property
    def config(self):
        """ 
        Return the config with capitalized keys to be consistent across local/remote APIs 
        """
        return self._config
    
    @property
    def power(self) -> bool:
        return True if self.config.get(MACHINE_MODE, False) == "BrewingMode" else False
    
    @property 
    def steam_boiler_enabled(self) -> bool:
        return self._config_steamboiler.get("isEnabled" , False)
    
    @property
    def is_heating(self) -> bool:
        coffee_heating = (float(self._config_coffeeboiler.get("current", 0)) < float(self._config_coffeeboiler.get("target", 0))) \
            and self.power 
        steam_heating = float(self._config_steamboiler.get("current", 0)) < float(self._config_steamboiler.get("target", 0)) \
            and self.power and self.steam_boiler_enabled
        return coffee_heating or steam_heating

    @property
    def brew_active(self) -> bool:
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
        self._current_status["coffee_boiler_on"]  = self._current_status.get("power", False)
        self._current_status["steam_boiler_on"] = self._current_status.get("steam_boiler_enable", False) \
            and self._current_status.get("power", False)
        return self._current_status
    

    '''
    *******************************************
    ***********  Functions ********************
    *******************************************
    '''

    def __init__(self):
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
        self._last_config_update   = None


    @classmethod
    async def create(cls, credentials):
        """ Initialize a cloud only client """
        self = cls()
        await self._init_cloud_api(credentials)
        return self


    @classmethod
    async def create_with_local_api(cls, credentials, ip, port=8081, use_websocket=False, use_bluetooth=False, bluetooth_scanner=None):
        """ Also initialize a local API client """
        self = cls()
        await self._init_cloud_api(credentials)
        await self._init_local_api(ip, port)

        if use_websocket:
            await self._init_websocket()

        if use_bluetooth:
            await self._init_bluetooth(credentials["username"], bluetooth_scanner=bluetooth_scanner)

        await self.update_local_machine_status(in_init=True)
        return self

    async def _init_cloud_api(self, credentials):
        self.client = await self._connect(credentials)
        self._machine_info = await self._get_machine_info()
        self._gw_url_with_serial = GW_MACHINE_BASE_URL + "/" + self.machine_info[SERIAL_NUMBER]
        self._firmware = await self.get_firmware()
        self._date_received = datetime.now()

    async def _init_local_api(self, ip, port=8081):
        """ init local connection client """
        self._lm_local_api = LMLocalAPI(local_ip=ip, local_port=port, local_bearer=self.machine_info[KEY])

    async def _init_websocket(self):
        """ Initiate the local websocket connection """
        _logger.debug("Initiating lmcloud with WebSockets")
        self._use_websocket = True
        asyncio.create_task(self._lm_local_api.websocket_connect())


    async def _init_bluetooth(self, username, init_client=True, bluetooth_scanner=None):
        """ Initiate the bluetooth connection """
        try:

            self._lm_bluetooth = await LMBluetooth.create(username=username, 
                                                    serial_number=self.machine_info[SERIAL_NUMBER],
                                                    token=self.machine_info[KEY],
                                                    init_client=init_client,
                                                    bleak_scanner=bluetooth_scanner)
        except BluetoothDeviceNotFound as e:
            _logger.warn(f"Could not find bluetooth device. Bluetooth commands will not be available and commands will all be sent through cloud.")
            _logger.debug(f"Full error: {e}")
        except BleakError as e:
            _logger.warn(f"Bleak encountered an error while trying to connect to bluetooth device. \
                            Maybe no bluetooth adapter is available? Bluetooth commands will not be available and commands will all be sent through cloud.")
            _logger.debug(f"Full error: {e}")


    async def _init_bluetooth_with_known_device(self, username, address, name):
        """ Initiate the bluetooth connection with a known device """
        self._lm_bluetooth = await LMBluetooth.create_with_known_device(username=username,
                                                                        serial_number=self.machine_info[SERIAL_NUMBER],
                                                                        token=self.machine_info[KEY],
                                                                        address=address, 
                                                                        name=name)

    async def _connect(self, credentials):
        """ Establish connection by building the OAuth client and requesting the token """

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

    async def websocket_connect(self, callback=None, use_sigterm_handler=True):
        await self._lm_local_api.websocket_connect(callback, use_sigterm_handler)

    def update_current_status(self, property_updated: str, value):
        """Update a property in the current status dict"""
        if property_updated != BREW_ACTIVE:
            self._current_status[property_updated] = value
        else:
            self._brew_active = value

    async def get_config(self):
        """Get configuration from cloud"""
        
        url = f"{self._gw_url_with_serial}/configuration"
        try:
            config = await self._rest_api_call(url=url, verb="GET")
            return config
        except Exception as e:
            _logger.warn(f"Could not get config from cloud. Full error: {e}")
            return self._config
        

    async def _update_config_obj(self, force_update=False):
        """Load the config into variables in this class"""

        if self._config and not bool(self._config):
            # wait at least 10 seconds between config updates to not flood the remote API
            if ((self._last_config_update and 
                (datetime.now() - self._last_config_update).total_seconds() < POLLING_DELAY_S) and not
                    force_update):
                return
        config = await self.get_config()
        if config and bool(config):
            self._config = config
        self._last_config_update = datetime.now()


    async def update_local_machine_status(self, in_init=False, force_update=False, local_api_retry_delay=3):
        """update config object"""

        if self._lm_local_api:
            try:
                try:
                    _logger.debug("Getting config from local API.")
                    self._config = await self._lm_local_api.local_get_config()
                except AuthFail as e:
                    _logger.debug("Got 403 from local API, sending token request to cloud.")
                    await self._token_command()
                    await asyncio.sleep(local_api_retry_delay)
                    self._config = await self._lm_local_api.local_get_config()
            except Exception as e:
                _logger.warn(f"Could not connect to local API although initialized")
                _logger.debug(f"Full error: {e}")
                await self._update_config_obj(force_update=force_update)

            if self._lm_local_api._timestamp_last_websocket_msg == None or (datetime.now() - self._lm_local_api._timestamp_last_websocket_msg).total_seconds() > 30: 
                if self._use_websocket and not in_init:  # during init we don't want to log this warning
                    _logger.warn("Could not get local machine status. Falling back to cloud status.")
            else:
                self._status = self._lm_local_api._status  # reference to the same object tp get websocket updates
        else:
            _logger.debug("Getting config from cloud.")
            await self._update_config_obj(force_update=force_update)

        self._config_coffeeboiler = next((item for item in self.config.get(BOILERS, []) if item["id"] == COFFEE_BOILER_NAME), {})
        self._config_steamboiler  = next((item for item in self.config.get(BOILERS, []) if item["id"] == STEAM_BOILER_NAME), {})

        await self._update_statistics_obj(force_update=force_update)
        self._date_received = datetime.now()
        self._current_status = self._build_current_status()


    async def get_statistics(self):
        """Get statistics"""
        _logger.debug("Getting statistics from cloud.")

        url = f"{self._gw_url_with_serial}/statistics/counters"
        try:
            statistics = await self._rest_api_call(url=url, verb="GET")
            return statistics
        except Exception as e:
            _logger.warn(f"Could not get statistics from cloud. Full error: {e}")
            return self._statistics   


    async def _update_statistics_obj(self, force_update=False):
        if self._statistics:
            # wait at least 10 seconds between config updates to not flood the remote API
            if (datetime.now() - self._last_statistics_update).total_seconds() < POLLING_DELAY_STATISTICS_S and not force_update:
                return
        self._statistics = await self.get_statistics()
        self._last_statistics_update = datetime.now() 



    async def _rest_api_call(self, url, verb="GET", data=None):
        """Wrapper for the API call"""

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
        """Wrapper for bluetooth commands"""
        if self._lm_bluetooth._client is None:
            return False
        
        try:
            await func(param)
            return True
        except BleakError as e:
            _logger.warn("Could not send command to bluetooth device, even though initalized. Falling back to cloud...")
            _logger.debug(f"Full error: {e}")
            return False
        

    async def _get_machine_info(self):
        """Get Basic machine info from the customer endpoint"""

        data = await self._rest_api_call(url=CUSTOMER_URL, verb="GET")

        machine_info = {}
        fleet = data.get("fleet", [{}])[0]
        
        machine_info[KEY] = fleet.get("communicationKey")

        if machine_info[KEY] is None:
            raise RequestNotSuccessful("communicationKey not part of response.")
        
        machine_info[MACHINE_NAME] = fleet.get("name")

        if machine_info[MACHINE_NAME] is None:
            raise RequestNotSuccessful("name not part of response.")
        
        machine = fleet.get("machine", {})
        machine_info[SERIAL_NUMBER] = machine.get("serialNumber")

        if machine_info[SERIAL_NUMBER] is None:
            raise RequestNotSuccessful("serialNumber not part of response.")
        
        machine_info[MODEL_NAME] = machine.get("model", {}).get("name")

        if machine_info[MODEL_NAME] is None:
            raise RequestNotSuccessful("model_name not part of response.")
        
        return machine_info
    

    async def get_firmware(self):
        """Get Firmware details"""

        url = f"{self._gw_url_with_serial}/firmware/"
        return await self._rest_api_call(url=url, verb="GET")

   
    async def set_power(self, enabled: bool):
        """Turn power of machine on or off"""

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
        """Turn Steamboiler on or off"""

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
        """Set steamboiler temperature (in Celsius)"""
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
        """Set coffee boiler temperature (in Celsius)"""

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
        """Enable/Disable Pre-Brew or Pre-Infusion (mutually exclusive)"""

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
        """Enable/Disable Pre-brew (Mode = Enabled)"""

        mode = "Enabled" if enabled else "Disabled"
        return await self._set_pre_brew_infusion(mode)


    async def set_preinfusion(self, enabled: bool):
        """Enable/Disable Pre-Infusion (Mode = TypeB)"""

        mode = "TypeB" if enabled else "Disabled"
        return await self._set_pre_brew_infusion(mode)


    async def configure_prebrew(self, prebrewOnTime=5000, prebrewOffTime=5000, key: int=1):
        '''
        Set Pre-Brew details
        Also used for preinfusion (prebrewOnTime=0, prebrewOnTime=ms)
        '''

        if type(prebrewOnTime) != int or type(prebrewOffTime) != int:
            msg = "Prebrew times must be in ms (integer)"
            _logger.debug(msg)
            raise TypeError(msg)
        
        if key < 1 or key > 4:
            msg = f"Key must be an integer value between 1 and 4, was {key}"
            _logger.debug(msg)
            raise ValueError(msg)
        
        if prebrewOnTime % 100 != 0 or prebrewOffTime % 100 != 0:
            msg = "Prebrew times must be multiple of 100"
            _logger.debug(msg)
            raise ValueError(msg)
        
        button = f"Dose{chr(key + 64)}"

        url = f"{self._gw_url_with_serial}/setting-preinfusion"
        data = {
            "button": button,
            "group": "Group1",
            "holdTimeMs": prebrewOffTime,
            "wetTimeMs": prebrewOnTime
        }
        response = await self._rest_api_call(url=url, verb="POST", data=data)

        self._config[PRE_INFUSION_SETTINGS]["Group1"][0]["preWetTime"] = prebrewOnTime % 1000
        self._config[PRE_INFUSION_SETTINGS]["Group1"][0]["preWetHoldTime"] = prebrewOffTime % 1000
        return response


    async def enable_plumbin(self, enable: bool):
        """Enable or disable plumbin mode"""

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
                "dose_index": dose_index,
                "dose_type": "PulsesType",
                "group": "Group1",
                "value": value
            }
        
        response = await self._rest_api_call(url=url, verb="POST", data=data)   
        if ("groupCapabilities" in self._config and
                len(self._config["groupCapabilities"]) > 0 and
                        "doses" in self._config["groupCapabilities"][0]):
                        idx = next(index for index, dose in enumerate(self._config["groupCapabilities"][0]["doses"]) if dose.get("doseIndex") == dose_index)
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
        """ Set auto-on/off schedule """
        url = f"{self._gw_url_with_serial}/scheduling"
        data = {"enable": enable, "days": schedule}
        response = await self._rest_api_call(url=url, verb="POST", data=data)
        self._config[WEEKLY_SCHEDULING_CONFIG] = schedule_in_to_out(enable, schedule)
        return response


    async def set_auto_on_off(self, day_of_week, hour_on, minute_on, hour_off, minute_off):
        """ Set auto-on/off for a day of the week """
        schedule = self.schedule
        idx = [index for (index, d) in enumerate(schedule) if d["day"][0:3] == day_of_week[0:3].upper()][0]
        schedule[idx]["enable"] = True
        schedule[idx]["on"] = f"{hour_on:02d}:{minute_on:02d}"
        schedule[idx]["off"] = f"{hour_off:02d}:{minute_off:02d}"
        return await self.configure_schedule(self.config[WEEKLY_SCHEDULING_CONFIG]["enabled"], schedule)
    

    async def set_auto_on_off_enable(self, day_of_week, enable):
        """ Enable or disable auto-on/off for a day of the week """
        schedule = self.schedule
        idx = [index for (index, d) in enumerate(schedule) if d["day"][0:3] == day_of_week[0:3].upper()][0]
        schedule[idx]["enable"] = enable
        return await self.configure_schedule(self.config[WEEKLY_SCHEDULING_CONFIG]["enabled"], schedule)
    


    async def start_backflush(self):
        """ Send command to start backflushing """
        url = f"{self._gw_url_with_serial}/enable-backflush"
        data = {"enable": True}
        response = await self._rest_api_call(url=url, verb="POST", data=data)
        self._config[BACKFLUSH_ENABLED] = True
        return response

    def _build_current_status(self):
        """ Build object which holds status for lamarzocco Home Assistant Integration """
        state = {
            "power":                        self.power,
            "enable_prebrewing":            True if self.config.get(PRE_INFUSION_SETTINGS, {}).get("mode") == "Enabled" else False,
            "enable_preinfusion":           True if self.config.get(PRE_INFUSION_SETTINGS, {}).get("mode") == "TypeB" else False,
            "steam_boiler_enable":          self.steam_boiler_enabled,
            "global_auto":                  self.config.get(WEEKLY_SCHEDULING_CONFIG, {}).get("enabled", False),
            "coffee_temp":                  self._config_coffeeboiler.get(CURRENT, 0),
            "coffee_set_temp":              self._config_coffeeboiler.get(TARGET, 0),
            "steam_temp":                   self._config_steamboiler.get(CURRENT, 0),
            "steam_set_temp":               self._config_steamboiler.get(TARGET, 0),
            "water_reservoir_contact":      self.config.get(TANK_STATUS, False),
            "plumbin_enable":               self.config.get(PLUMBED_IN, False),
            "date_received:":               self.date_received,
            "machine_name":                 self.machine_info.get(MACHINE_NAME),
            "model_name":                   self.machine_info.get(MODEL_NAME),
            "update_available":             self.firmware_version != self.latest_firmware_version,
            "heating_state":                self.heating_state,
        }

        doses = parse_doses(self.config)
        preinfusion_settings = parse_preinfusion_settings(self.config)
        schedule = schedule_out_to_hass(self.config)
        statistics = parse_statistics(self.statistics)
        return state | doses | preinfusion_settings | schedule | statistics

    async def _token_command(self):
        url = f"{self._gw_url_with_serial}/token-request"
        response = await self._rest_api_call(url=url, verb="GET")
        commandId = response.get("commandId")
        if commandId is None:
            return

        url = f"{GW_AWS_PROXY_BASE_URL}/{self.serial_number}/commands/{commandId}"
        response = await self._rest_api_call(url=url, verb="GET")
        return response

