import aiohttp
import websockets
import asyncio
import signal
import json
from datetime import datetime
from .const import *
from .helpers import *
import logging

_logger = logging.getLogger(__name__)

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
    def brew_active(self):
        return self._status[BREW_ACTIVE]
    
    @property
    def brew_active_duration(self):
        return self._status[BREW_ACTIVE_DURATION]

    def __init__(self, local_ip, local_bearer, local_port=8081):
        self._local_ip = local_ip
        self._local_port = local_port
        self._local_bearer = local_bearer

        # init local variables
        self._full_config = None
        self._timestamp_last_websocket_msg = None

        self._status = {}

        self._status[BREW_ACTIVE] = False
        self._status[BREW_ACTIVE_DURATION] = 0


    '''
    Get current config of machine from local API
    '''
    async def local_get_config(self):
        headers = {"Authorization": f"Bearer {self._local_bearer}"}
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(f"http://{self._local_ip}:{self._local_port}/api/v1/config") as response:
                if response.status == 200:
                    return await response.json()
                
    async def websocket_connect(self, callback = None):
        headers = {"Authorization": f"Bearer {self._local_bearer}"}
        async for websocket in websockets.connect(f"ws://{self._local_ip}:{self._local_port}/api/v1/streaming", extra_headers=headers):
            try:
                # Close the connection when receiving SIGTERM.
                loop = asyncio.get_running_loop()
                loop.add_signal_handler(
                    signal.SIGTERM, loop.create_task, websocket.close())

                # Process messages received on the connection.
                async for message in websocket:
                    await self.handle_websocket_message(message)
                    if callback:
                        callback(self._status)
            except websockets.ConnectionClosed:
                await asyncio.sleep(20) # wait 20 seconds before trying to reconnect
                continue
            except Exception as e:
                _logger.error(f"Error during websocket connection: {e}")
                await asyncio.sleep(20)
                continue

    async def handle_websocket_message(self, message):
        try:
            self._timestamp_last_websocket_msg = datetime.now()
            message = json.loads(message)
            if type(message) is dict:
                if message["name"] == "SteamBoilerUpdateTemperature":
                    self._status["SteamTemperature"] = message["value"]
                elif message["name"] == "CoffeeBoiler1UpdateTemperature":
                    self._status["CoffeeTemperature"] = message["value"]
                elif message["name"] == "MachineConfiguration":
                    self._full_config = message["value"]
                    self._status["TankLevel"] = message["value"]
            if type(message) is list:
                if message[0]["name"] == "BrewingUpdateGroup1Time":
                    self._status[BREW_ACTIVE_DURATION] = message[0]["value"]
                elif message[0]["name"] in ["BrewingStartedGroup1StopType", "BrewingStartedGroup1DoseIndex"]:
                    # started active brew
                    self._status[BREW_ACTIVE] = True
                elif message[0]["name"] in ["BrewingSnapshotGroup1", "FlushStoppedGroup1DoseIndex", "FlushStoppedGroup1Time"]:
                    # stopped active brew
                    self._status[BREW_ACTIVE] = False
        except Exception as e:
            _logger.error(f"Error during handling of websocket message: {e}")