# La Marzocco Client
This is a library to interface with La Marzocco's Home machines.
It also has support to get information for the Pico grinder.



# Libraries in this project
- `LaMarzoccoLocalClient` calls the new local API the Micra exposes, using the Bearer token from the customer cloud endpoint. However, this API currently only supports getting the config, and some status objects (like shottimer) over websockets, but does not support setting anything (to my knowledge). Local settings appear to only happen through [Bluetooth connections](#lmbluetooth). 
- `LaMarzoccoCloudClient` interacts with `gw-lmz.lamarzocco.com` to send commands. lmcloud can be initialized to only issue remote commands, or to initialize an instance of `lmlocalapi` for getting the current machine settings. This helps to avoid flooding the cloud API and is faster overall.
- `LaMarzoccoBluetoothClient` provides a bluetooth client to send settings to the machine via bluetooth

# Setup

## LaMarzoccoCloudClient


You need `username` and `password` which are the credentials you're using to sign into the La Marzocco Home app.


It is initialized like this
```python
cloud_client = await LaMarzoccoCloudClient.create(username, password)
```

## LaMarzoccoLocalClient
If you just want to run the local API you need the IP of your machine, the Port it is listening on (8081 by default), the Bearer token (`communicationKey`) used for local communication. 
You can obtain that key by inspecting a call to `https://cms.lamarzocco.io/api/customer`, while connected to `mitmproxy` (process above), or making a new (authenticated) call to that endpoint. 

Then you can init the class with 
```python
local_client = LaMarzoccoLocalClient(ip, local_token)
```


## LaMarzoccoBluetoothClient
Some commands, like turning the machine on and off are always sent through bluetooth whenever possible. The available bluetooth characteristics are described in [bluetooth_characteristics](docs/bluetooth_characteristics.md).
The class `LaMarzoccoBluetoothClient` discovers any bluetooth devices connects to it. Then we can send local bluetooth commands.

To use Bluetooth you can either init LMCloud with
```python
    if bluetooth_devices := LaMarzoccoBluetoothClient.discover_devices():
        print("Found bluetooth device:", bluetooth_devices[0])

    bluetooth_client = LaMarzoccoBluetoothClient(
        username,
        serial_number,
        local_token
        bluetooth_devices[0],
    )
```

The local_token is the same token you need to initialize the local API, which you need to get from LM's cloud once. The serial number is your machine's serial number and the username is the email of your LaMarzocco account.


## Machine
Once you have any or all of the clients, you can initialize a machine object with
```python
machine = Machine.create(model, serial_number, name, cloud_client, local_client, bluetooth_client)
```

You can then use the machine object to send commands to the machine, or to get the current status of the machine. If you're running in cloud only mode, please be mindful with the requests to not flood the cloud API.

## Grinder
The Pico grinder can be initialized with
```python
grinder = LaMarzoccoGrinder.create(model, serial_number, name, cloud_client, local_client, bluetooth_client)
```
where you can use the same cloud client as for the machine, but you need to initialize new local and bluetooth clients (the same way as for the machine) to use the grinder.

### Websockets
The local API initiates a websocket connection to
```
http://{IP}:8081/api/v1/streaming
```
The packets which are received on that WebSocket are documented in [websockets](docs/websockets.md)

If WebSockets are enabled the shot timer becomes available to use, however as long as the library is running in WebSocket mode, the App will no longer be able to connect.

To use WebSockets start the integration with
```python
await machine.websocket_connect(callback)
```
with an optional callback function that will be called whenever there have been updates for the machine from the websocket.