# La Marzocco Client
This is a library to interface with La Marzocco's "new" Home machines (currently only the Micra).

It's in experimentals stages and meant mainly to connect to the Micra, as for the other IoT enabled machines you can use the [lmdirect](https://github.com/rccoleman/lmdirect) library.

# Libraries in this project
- `lmlocalapi` calls the new local API the Micra exposes, using the Bearer token from the customer cloud endpoint. However, this API currently only supports getting the config, and some status objects (like shottimer) over websockets, but does not support setting anything (to my knowledge). Local settings appear to only happen through [Bluetooth connections](#lmbluetooth). If La Marzocco updates the firmware or more endpoints are found this library will be updated to reflect those additional endpoints.
- `lmcloud` interacts with `gw.lamarzocco.com` to send commands. lmcloud can be initialized to only issue remote commands, or to initialize an instance of `lmlocalapi` for getting the current machine settings. This helps to avoid flooding the cloud API and is faster overall.
- `lmbluetooth` provides a bluetooth client to send settings to the machine via bluetooth

Because of that reason the config object `self._config` in the lmcloud instance without utilizing the local API will always at least be 10 seconds old. This is to avoid automatic property checks (e.g. from HomeAssistant) to spam the cloud API. If you really require a most recent config you can call the method `get_config()`.

# Setup

## lmcloud
To run `lmcloud` you will first need to create a dict, containing `clientId`, `clientSecret`, `username` and `password`.

`username` and `password` are easy to get because those are the credentials you're using to sign into the La Marzocco Home app.

`clientId` and `clientSecret` are harder to get. The "easiest" way is to configure `mitmproxy` on a PC, configure your WiFi settings on your phone to use that proxy. Then log out of your La Marzocco App, sign in again and watch for a call to `https://cms.lamarzocco.io/oauth/v2/token`. The  credentials you're looking for will be in that call.
More of the calls are documented in [remote_rest](docs/remote_rest.md).

You then need to create a file called `config.json` looking like this:
```json
{
    "client_id": "long_string",
    "client_secret": "long_string",
    "username": "email",
    "password": "password",
    "host": "192.168.1.123" # optional, only if you want the local API
}
```

Which then needs to be passed into a dictionary:

```python
with open("config.json") as f:
    data = json.load(f)

creds = {
    "client_id": data["client_id"],
    "client_secret": data["client_secret"],
    "username": data["username"],
    "password": data["password"]
}

```

`lmcloud` exposes two classmethods: One to build an instance with the local API, and one to build an instance relying entirely on cloud functions. 

It is initialized like this
```python
lm_cloud = await LMCloud.create(creds) # cloud only
lm_cloud = await LMCloud.create_with_local_api(creds, ip=ip) # with local API
```

## lmlocalapi
If you just want to run the local API you need the IP of your machine, the Port it is listening on (8081 by default), the Bearer token (`communicationKey`) used for local communication. 
You can obtain that key by inspecting a call to `https://cms.lamarzocco.io/api/customer`, while connected to `mitmproxy` (process above), or making a new (authenticated) call to that endpoint. `lmcloud` will also connect to this endpoint so you could also used a breakpoint there to get this key, which is stored in a key called `communicationKey`.

Then you can init the class with 
```python
lm_local_api = LMLocalAPI(ip, bearer)
```

### Websockets
The local API initiates a websocket connection to
```
http://{IP}:8081/api/v1/streaming
```
The packets which are received on that WebSocket are documented in [websockets](docs/websockets.md)

If WebSockets are enabled the shot timer becomes available to use, however as long as the library is running in WebSocket mode, the App will no longer be able to connect.

To use WebSockets start the integration with
```python
lm = await LMCloud.create_with_local_api(creds, <IP>, port=8081, use_websockets=True)

while True:
    print(lm._lm_local_api.active_brew) # is a brew running at the moment
    print(lm._lm_local_api.active_brew_duration) # the current shot timer returned by the machine
```


## lmbluetooth
Some commands, like turning the machine on and off are always sent through bluetooth whenever possible. The available bluetooth characteristics are described in [bluetooth_characteristics](docs/bluetooth_characteristics.md).
The class `LMBluetooth` discovers any bluetooth devices with `Micra` in the name and connects to it. Then we can send local bluetooth commands.

To use Bluetooth you can either init LMCloud with
```python
    lm = await LMCloud.create_with_local_api(creds, <IP>, port=8081, use_bluetooth=True)
```

or even init the Bluetooth client standalony
```python
    lm_bt = await LMBluetooth.create(username, serial_number, token)
```

The token is the same token you need to initialize the local API, which you need to get from LM's cloud once. The serial number is your machine's serial number and the username is the email of your LaMarzocco account.