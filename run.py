from lmcloud.lmcloud import LMCloud
import json
import asyncio

async def main():
    with open("config.json") as f:
        data = json.load(f)

    creds = {
        "client_id": data["client_id"],
        "client_secret": data["client_secret"],
        "username": data["username"],
        "password": data["password"]
    }

    # lmcloud = await LMCloud.create(creds)
    lmcloud = await LMCloud.create_with_local_api(creds, data["host"], data["port"])
    # await lmcloud.set_power("standby")
    # lmcloud.local_get_config()
    # await lmcloud.set_steam(True)
    #await lmcloud.set_coffee_temp(93.5) 
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
    #await lmcloud.set_prebrew(False)
    # config = await lmcloud.get_config()
    await asyncio.sleep(10)
    await lmcloud.update_local_machine_status()
    print("Entering loop...")
    while True:
        # print(lmcloud._lm_local_api._timestamp_last_websocket_msg)
        if lmcloud.current_status["active_brew"]:
            print("Brewing")
        await asyncio.sleep(1)

    print("Done")

asyncio.run(main())