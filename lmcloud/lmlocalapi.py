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
This class is for interaction with the new local API
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
                
    async def websocket_connect(self, callback=None, use_sigterm_handler=True) -> None:
        headers = {"Authorization": f"Bearer {self._local_bearer}"}
        async for websocket in websockets.connect(f"ws://{self._local_ip}:{self._local_port}/api/v1/streaming", extra_headers=headers):
            try:
                if use_sigterm_handler:
                    # Close the connection when receiving SIGTERM.
                    loop = asyncio.get_running_loop()
                    loop.add_signal_handler(
                        signal.SIGTERM, loop.create_task, websocket.close())
                # Process messages received on the connection.
                async for message in websocket:
                    property_updated, value = await self.handle_websocket_message(message)
                    if callback:
                        callback(property_updated, value)
            except websockets.ConnectionClosed:
                _logger.debug(f"Websocket disconnected, reconnecting in {WEBSOCKET_RETRY_DELAY}...")
                await asyncio.sleep(WEBSOCKET_RETRY_DELAY)  # wait 20 seconds before trying to reconnect
                continue
            except Exception as e:
                _logger.error(f"Error during websocket connection: {e}")

    async def handle_websocket_message(self, message):
        try:
            self._timestamp_last_websocket_msg = datetime.now()
            message = json.loads(message)
            unmapped_msg = False

            if type(message) is dict:

                if 'MachineConfiguration' in message:
                    # got machine configuration
                    value = json.loads(message["MachineConfiguration"])
                    self._status["machineConfiguration"] = value
                    return "machineConfiguration", value
                
                elif "SystemInfo" in message:
                    value = json.loads(message["SystemInfo"])
                    self._status["systemInfo"] = value
                    return "systemInfo", value
                else:
                    unmapped_msg = True

            elif type(message) is list:

                if "KeepAlive" in message[0]:
                    return None, None
                
                elif "SteamBoilerUpdateTemperature" in message[0]:
                    value = message[0]["SteamBoilerUpdateTemperature"]
                    self._status["steamTemperature"] = value
                    return "steam_temp", value
                
                elif "CoffeeBoiler1UpdateTemperature" in message[0]:
                    value = message[0]["CoffeeBoiler1UpdateTemperature"]
                    self._status["coffeeTemperature"] = value
                    return "coffee_temp", value

                elif "Sleep" in message[0]:
                    self._status["power"] = False
                    self._status["sleepCause"] = message[0]["Sleep"]
                    return "power", False
                
                elif "WakeUp" in message[0]:
                    self._status["power"] = True
                    self._status["wakeupCause"] = message[0]["WakeUp"]
                    return "power", True
                
                elif "MachineStatistics" in message[0]:
                    value = json.loads(message[0]["MachineStatistics"])
                    self._status["statistics"] = value
                    return "statistics", value
                
                elif "BrewingUpdateGroup1Time" in message[0]:
                    self._status[BREW_ACTIVE] = True
                    self._status[BREW_ACTIVE_DURATION] = message[0]["BrewingUpdateGroup1Time"]
                    return BREW_ACTIVE, True
                
                elif "BrewingStartedGroup1StopType" in message[0]:
                    return None, None
                
                elif "BrewingSnapshotGroup1" in message[0]:
                    self._status[BREW_ACTIVE] = False
                    self._status["brewingSnapshot"] = json.loads(message[0]["BrewingSnapshotGroup1"])
                    return BREW_ACTIVE, False
                else:
                    unmapped_msg = True
            else:
                unmapped_msg = True

            if unmapped_msg:
                _logger.warn(f"Unmapped message from La Marzocco WebSocket, please report to dev: {message}")

            return None, None

        except Exception as e:
            _logger.error(f"Error during handling of websocket message: {e}")