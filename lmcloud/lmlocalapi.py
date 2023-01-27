import requests
from .const import *
from .helpers import *

'''
This class is for interaction with the new local API currently only the Micra exposes
'''
class LMLocalAPI:

    @property
    def local_port(self):
        return self._local_port
    
    @property
    def local_ip(self):
        return self._local_ip

    # current power status / machine mode (on/standby)
    def get_machine_mode(self):
        return self.local_get_config()[MACHINE_MODE]

    def get_coffee_boiler_enabled(self):
        boilers = self.local_get_config()["boilers"]
        coffee_boiler = next(item for item in boilers if item["id"] == COFFEE_BOILER_NAME)
        return coffee_boiler["isEnabled"]

    def get_steam_boiler_enabled(self):
        boilers = self.local_get_config()["boilers"]
        coffee_boiler = next(item for item in boilers if item["id"] == STEAM_BOILER_NAME)
        return coffee_boiler["isEnabled"]

    def get_steam_temp(self):
        return self.local_get_config()[BOILER_TARGET_TEMP][STEAM_BOILER_NAME]

    def get_coffee_temp(self):
        return self.local_get_config()[BOILER_TARGET_TEMP][COFFEE_BOILER_NAME]

    def get_plumbin_enabled(self):
        return self.local_get_config()[PLUMBED_IN]

    def get_preinfusion_settings(self):
        return self.local_get_config()[PRE_INFUSION_SETTINGS]

    def get_schedule(self):
        return convert_schedule(self.local_get_config()[WEEKLY_SCHEDULING_CONFIG])

    def __init__(self, local_ip, local_bearer, local_port=8081):
        self._local_ip = local_ip
        self._local_port = local_port
        self._local_bearer = local_bearer


    '''
    Get current config of machine from local API
    '''
    def local_get_config(self):
        headers = {"Authorization": f"Bearer {self._local_bearer}"}
        response = requests.get(f"http://{self._local_ip}:{self._local_port}/api/v1/config", headers=headers)
        if response.status_code == 200:
            return response.json()["data"]

    