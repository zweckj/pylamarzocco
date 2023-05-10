import asyncio
from bleak import BleakScanner, BleakClient

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
                if  "MICRA" in d.name:
                    self.address = d.address
                    self.name = d.name


    async def set_power(self, state: bool):
        """
        Power on the machine
        """
        mode = "BrewingMode" if state else "StandBy"
        msg = "{\"name\":\"MachineChangeMode\",\"parameter\":{\"mode\":\"" + mode + "\"}}"
        async with BleakClient(self.address) as client:
            if client.is_connected:
                await client.write_gatt_char(TODO, bytes(msg, 'utf-8'))
            else:
                pass

    async def set_power(self, state: bool):
        """
        Power on steam
        """
        msg = "{\"name\":\"SettingBoilerEnable\",\"parameter\":{\"identifier\":\"SteamBoiler\",\"state\":" + state + "}}"
        async with BleakClient(self.address) as client:
            if client.is_connected:
                await client.write_gatt_char(TODO, bytes(msg, 'utf-8'))
            else:
                pass