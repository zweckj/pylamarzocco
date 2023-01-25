from lmcloud.lmcloud import LMCloud
from lmcloud.credentials import Credentials
import json
import asyncio

async def main():
    with open("config.json") as f:
        data = json.load(f)

    creds = Credentials(
        client_id=data["client_id"],
        client_secret=data["client_secret"],
        username=data["username"],
        password=data["password"]
    )

    lmcloud = await LMCloud.create(creds, data["host"], data["port"])
    # await lmcloud.set_power("standby")
    # lmcloud.local_get_config()
    # await lmcloud.set_steam(True)
    #await lmcloud.set_coffee_temp(93.5)
    await lmcloud.set_steam_temp(131)

asyncio.run(main())