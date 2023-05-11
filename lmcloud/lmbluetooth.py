import asyncio
from bleak import BleakScanner, BleakClient
from .const import WRITE_SETTINGS_CHARACTERISTIC, MODEL_LMU

class LMBluetooth:
    """
    class to interact with machine via Bluetooth
    """

    def __init__(self):
      self.address = None
      self.name = None


    @classmethod
    async def create(cls, bleak_scanner=None):
        """
        Init class by scanning for devices and selecting the first one with "MICRA" in the name
        """
        self = cls()
        if bleak_scanner is None:
            async with BleakScanner() as scanner:
                await self.discover_device(scanner)
        else:
            await self.discover_device(bleak_scanner)
        return self

    async def discover_device(self, scanner):
        devices = await scanner.discover()
        for d in devices:
            if d.name:
                if MODEL_LMU.upper() in d.name:
                    self.address = d.address
                    self.name = d.name

    
    async def write_bluetooth_message(self, address: str, message: str):
        async with BleakClient(self.address) as client:
            if client.is_connected:
                await client.write_gatt_char(WRITE_SETTINGS_CHARACTERISTIC, bytes(message, 'utf-8'))
            else:
                pass

    async def set_power(self, state: bool):
        """
        Power on the machine
        """
        mode = "BrewingMode" if state else "StandBy"
        msg = "{\"name\":\"MachineChangeMode\",\"parameter\":{\"mode\":\"" + mode + "\"}}"
        self.write_bluetooth_message(self.address, msg)

    async def set_power(self, state: bool):
        """
        Power on steam
        """
        msg = "{\"name\":\"SettingBoilerEnable\",\"parameter\":{\"identifier\":\"SteamBoiler\",\"state\":" + state + "}}"
        self.write_bluetooth_message(self.address, msg)

    async def set_steam_temp(self, temperature:int):
        '''
        Set steamboiler temperature (in Celsius)
        '''
        if not temperature == 131 and not temperature == 128 and not temperature == 126:
            msg = "Steam temp must be one of 126, 128, 131 (°C)"
            raise ValueError(msg)
        else:
            msg = "{\"name\":\"SettingBoilerTarget\",\"parameter\":{\"identifier\":\"SteamBoiler\",\"value\":" +  str(temperature) + "}}"
            self.write_bluetooth_message(self.address, msg)

    async def set_coffee_temp(self, temperature:int):
        '''
        Set Cofeeboiler temperature (in Celsius)
        '''
        msg = "{\"name\":\"SettingBoilerTarget\",\"parameter\":{\"identifier\":\"CoffeeBoiler1\",\"value\":" +  str(temperature) + "}}"
        self.write_bluetooth_message(self.address, msg)
