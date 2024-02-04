"""Sample class to testrun"""

import json
import asyncio

from lmcloud.lm_cloud import LaMarzoccoCloudClient
from lmcloud.lm_iot_device import LaMarzoccoIoTDevice
from lmcloud.lm_machine import LaMarzoccoMachine
from lmcloud.const import LaMarzoccoMachineModel
from lmcloud.lm_bluetooth import LaMarzoccoBluetoothClient
from lmcloud.lm_local import LaMarzoccoLocalClient


async def main():
    """Main function."""
    with open("config.json") as f:
        data = json.load(f)

    cloud_client = await LaMarzoccoCloudClient.create(
        username=data["username"],
        password=data["password"],
    )
    fleet = await cloud_client.get_customer_fleet()

    local_client = LaMarzoccoLocalClient(
        host=data["host"],
        local_bearer=fleet[0].communication_key,
    )

    # bluetooth_client =  await LaMarzoccoBluetoothClient.create()
    LaMarzoccoIoTDevice.cloud_client = cloud_client
    machine = LaMarzoccoMachine(
        model=LaMarzoccoMachineModel(fleet[0].model_name),
        serial_number=fleet[0].serial_number,
        name=fleet[0].name,
        local_client=local_client,
    )

    await machine.websocket_connect()

    # lmcloud = await LMCloud.create_with_local_api(creds, data["host"], data["port"])
    # await lmcloud.set_power("standby")
    # lmcloud.local_get_config()
    # await lmcloud.set_steam(True)
    # await lmcloud.set_coffee_temp(93.5)
    # await lmcloud.set_steam_temp(131)
    # print(await lmcloud.get_coffee_boiler_enabled())

    # await lmcloud.get_status()
    # config = await lmcloud.get_config()
    # await lmcloud.set_steam(False)
    # await lmcloud.set_auto_on_off("Monday", 13, 15, 16, 15)
    # await lmcloud.set_auto_on_off_enable("Monday", False)
    # current_status = await lmcloud._get_status()
    # await lmcloud.set_steam(True)
    # current_status = lmcloud.current_status
    # await lmcloud.set_prebrew(False)
    # config = await lmcloud.get_config()
    # await asyncio.sleep(10)
    # await lmcloud.update_local_machine_status()
    # print("Entering loop...")
    # while True:
    #     # print(lmcloud._lm_local_api._timestamp_last_websocket_msg)
    #     if lmcloud.current_status["active_brew"]:
    #         print("Brewing")
    #     await asyncio.sleep(1)

    await machine.set_power(True)
    await asyncio.sleep(5)
    await machine.set_power(False)

    # while True:
    #     print("waiting...")
    #     # print(lmcloud._lm_local_api._timestamp_last_websocket_msg)
    #     # if lmcloud.current_status["brew_active"]:
    #     #     print("Brewing")#
    #    # await lmcloud.update_local_machine_status()
    #     await asyncio.sleep(5)
    # print(lmcloud._lm_bluetooth._address)
    # await lmcloud.set_power(True)
    # await lmcloud.set_steam(False)
    # await lmcloud.set_coffee_temp(93.5)
    # await lmcloud.set_steam_temp(128)
    # await lmcloud.set_power(False)
    # await lmcloud.set_auto_on_off("thu", 14, 15, 16, 15)
    # await lmcloud.set_auto_on_off_enable("thu", False)

    print(str(machine))
    print("Done.")


asyncio.run(main())
