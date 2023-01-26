import requests
from .const import *

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
    @property
    def machine_mode(self):
        return self.local_get_config()[MACHINE_MODE]

    @property 
    def steam_temp(self):
        return self.local_get_config()[BOILER_TARGET_TEMP][STEAM_BOILER_NAME]

    @property
    def coffee_temp(self):
        return self.local_get_config()[BOILER_TARGET_TEMP][COFFEE_BOILER_NAME]

    def __init__(self, local_ip, local_port, local_bearer):
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

    