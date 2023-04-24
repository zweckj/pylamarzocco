import aiohttp
import websockets
import asyncio
import signal
import json
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
    
    @property
    def coffee_temp(self):
        return self._coffee_temp
    
    @property
    def steam_temp(self):
        return self._steam_temp
    
    @property
    def water_reservoir_contact(self):
        return self._full_config["tankStatus"]
    
    @property
    def active_brew(self):
        return self._active_brew
    
    @property
    def active_brew_duration(self):
        return self._active_brew_duration

    def __init__(self, local_ip, local_bearer, local_port=8081):
        self._local_ip = local_ip
        self._local_port = local_port
        self._local_bearer = local_bearer

        # init local variables
        self._full_config = None
        self._coffee_temp = 0
        self._steam_temp = 0
        self._active_brew = False
        self._active_brew_duration = 0


    '''
    Get current config of machine from local API
    '''
    async def local_get_config(self):
        headers = {"Authorization": f"Bearer {self._local_bearer}"}
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(f"http://{self._local_ip}:{self._local_port}/api/v1/config") as response:
                if response.status == 200:
                    return await response.json()
                
    async def websocket_connect(self):
        headers = {"Authorization": f"Bearer {self._local_bearer}"}
        async for websocket in websockets.connect(f"ws://{self._local_ip}:{self._local_port}/api/v1/streaming", extra_headers=headers):
            try:
                print("Was here")
                # Close the connection when receiving SIGTERM.
                loop = asyncio.get_running_loop()
                loop.add_signal_handler(
                    signal.SIGTERM, loop.create_task, websocket.close())

                # Process messages received on the connection.
                async for message in websocket:
                    await self.handle_websocket_message(message)
            except websockets.ConnectionClosed:
                continue

    async def handle_websocket_message(self, message):
        try:
            message = json.loads(message)
            print(message)
            if type(message) is dict:
                if message["name"] == "SteamBoilerUpdateTemperature":
                    self._steam_temp = message["value"]
                elif message["name"] == "CoffeeBoiler1UpdateTemperature":
                    self._coffee_temp = message["value"]
                elif message["name"] == "MachineConfiguration":
                    self._full_config = message["value"]
            elif type(message) is list:
                if message[0]["name"] == "BrewingUpdateGroup1Time":
                    self._active_brew_duration = message[0]["value"]
                elif message[0]["name"] in ["BrewingStartedGroup1StopType", "BrewingStartedGroup1DoseIndex"]:
                    # started active brew
                    self._active_brew = True
                elif message[0]["name"] in ["BrewingSnapshotGroup1", "FlushStoppedGroup1DoseIndex", "FlushStoppedGroup1Time"]:
                    # stopped active brew
                    self._active_brew = False
        except Exception as e:
            print(f"Error during handling of websocket message: {e}")