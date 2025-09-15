"""Demonstrate the usage of the library."""

import asyncio
import uuid
from pathlib import Path

from aiohttp import ClientSession

from pylamarzocco import LaMarzoccoCloudClient, LaMarzoccoMachine
from pylamarzocco.models import ThingDashboardWebsocketConfig
from pylamarzocco.util import InstallationKey, generate_installation_key

SERIAL = ""
USERNAME = ""
PASSWORD = ""


async def main():
    """Async main."""
    # Generate or load key material
    registration_required = False
    key_file = Path("installation_key.json")
    if not key_file.exists():
        print("Generating new key material...")
        installation_key = generate_installation_key(str(uuid.uuid4()).lower())
        print("Generated key material:")
        with open(key_file, "w", encoding="utf-8") as f:
            f.write(installation_key.to_json())
        registration_required = True
    else:
        print("Loading existing key material...")
        with open(key_file, "r", encoding="utf-8") as f:
            installation_key = InstallationKey.from_json(f.read())

    async with ClientSession() as session:
        client = LaMarzoccoCloudClient(
            username=USERNAME,
            password=PASSWORD,
            installation_key=installation_key,
            client=session,
        )
        if registration_required:
            print("Registering device...")
            await client.async_register_client()
        machine = LaMarzoccoMachine(SERIAL, client)

        await machine.get_dashboard()
        await machine.get_firmware()
        await machine.get_schedule()
        await machine.get_settings()
        await machine.get_statistics()
        print(machine.to_dict())

        def my_callback(config: ThingDashboardWebsocketConfig):
            print(
                "----------------------------- NEW MESSAGE ----------------------------"
            )
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
