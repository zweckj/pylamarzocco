"""Demonstrate the usage of the library."""

import asyncio

from pylamarzocco import LaMarzoccoCloudClient, LaMarzoccoMachine
from pylamarzocco.models import ThingDashboardWebsocketConfig


SERIAL = ""
USERNAME = ""
PASSWORD = ""

async def main():
    """Async main."""
    client = LaMarzoccoCloudClient(username=USERNAME, password=PASSWORD)
    machine = LaMarzoccoMachine(SERIAL, client)

    await machine.get_dashboard()
    await machine.get_firmware()
    await machine.get_schedule()
    await machine.get_settings()
    await machine.get_statistics()
    print(machine.to_dict())

    def my_callback(config: ThingDashboardWebsocketConfig):
        print("----------------------------- NEW MESSAGE ----------------------------")
        print(f"Received: {config.to_dict()}")

    asyncio.create_task(machine.connect_dashboard_websocket(my_callback))
    print("----------------------------- TURNING ON ----------------------------")
    await machine.set_power(True)
    await asyncio.sleep(5)
    print("----------------------------- TURNING OFF ----------------------------")
    await machine.set_power(False)
    print("----------------------------- WAITING ----------------------------")
    await asyncio.sleep(10)
    await machine.websocket.disconnect()



asyncio.run(main())
