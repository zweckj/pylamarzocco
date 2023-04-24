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

    def __init__(self, local_ip, local_bearer, local_port=8081):
        self._local_ip = local_ip
        self._local_port = local_port
        self._local_bearer = local_bearer


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
                    pass
                elif message["name"] == "CoffeeBoiler1UpdateTemperature":
                    pass
            elif type(message) is list:
                if message[0]["name"] == "BrewingUpdateGroup1Time":
                    pass
                elif message[0]["name"] in ["BrewingStartedGroup1StopType", "BrewingStartedGroup1DoseIndex"]:
                    # started active brew
                    pass
                elif message[0]["name"] in ["BrewingSnapshotGroup1", "FlushStoppedGroup1DoseIndex", "FlushStoppedGroup1Time"]:
                    # stopped active brew
                    pass
        except Exception as e:
            print(f"Error during handling of websocket message: {e}")