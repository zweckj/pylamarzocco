# La Marzocco Python Client

This is a library to interface with La Marzocco's Home machines.

![workflow](https://github.com/zweckj/pylamarzocco/actions/workflows/pypi.yaml/badge.svg)
[![codecov](https://codecov.io/gh/zweckj/pylamarzocco/graph/badge.svg?token=350GPTLZXS)](https://codecov.io/gh/zweckj/pylamarzocco)

> [!NOTE]
> This is an unofficial library, that is not affiliated with, endorsed by, or sponsored by La Marzocco S.r.l in any way. "La Marzocco" and machine names are trademarks of their respective owner, used only to describe what this library talks to.

# Installing this libary
This project is on pypi and can be installed using pip

```bash
pip install pylamarzocco
```

# Libraries in this project

- `LaMarzoccoCloudClient` interacts with La Marzocco's cloud API to send commands and retrieve machine information. It also supports WebSocket connections for real-time updates.
- `LaMarzoccoBluetoothClient` provides a bluetooth client to send settings to the machine via bluetooth.
- `LaMarzoccoMachine` provides a high-level interface for interacting with La Marzocco machines, combining both cloud and bluetooth clients.

# Setup

## LaMarzoccoCloudClient

You need `username` and `password`, which are the credentials you're using to sign into the La Marzocco Home app. Additionally, you need an `InstallationKey` for authentication.

### Generating Installation Key

First, generate an installation key for your client:

```python
import uuid
from pylamarzocco.util import generate_installation_key, InstallationKey

# Generate new key material
installation_key = generate_installation_key(str(uuid.uuid4()).lower())

# Save it for future use
with open("installation_key.json", "w", encoding="utf-8") as f:
    f.write(installation_key.to_json())

# Or load existing key material
with open("installation_key.json", "r", encoding="utf-8") as f:
    installation_key = InstallationKey.from_json(f.read())
```

### Initializing the Client

```python
from aiohttp import ClientSession
from pylamarzocco import LaMarzoccoCloudClient

async with ClientSession() as session:
    cloud_client = LaMarzoccoCloudClient(
        username=username,
        password=password,
        installation_key=installation_key,
        client=session,
    )
    
    # Register the client (only needed once for new installation keys)
    await cloud_client.async_register_client()
```



## LaMarzoccoBluetoothClient

The `LaMarzoccoBluetoothClient` discovers bluetooth devices and connects to them to send local bluetooth commands. Some commands, like turning the machine on and off, can be sent through bluetooth.

### Obtaining the Bluetooth Token

Before you can use the Bluetooth client, you need to obtain the Bluetooth authentication token. There are three ways to get this token:

#### Method 1: Through the Cloud Client

The easiest method is to retrieve the token from the cloud API after initializing the cloud client:

```python
from pylamarzocco import LaMarzoccoCloudClient

# Initialize and authenticate with the cloud client
cloud_client = LaMarzoccoCloudClient(
    username=username,
    password=password,
    installation_key=installation_key,
    client=session,
)

# Get all machines associated with your account
things = await cloud_client.list_things()

# The token is available in the ble_auth_token field
ble_token = things[0].ble_auth_token
```

#### Method 2: Through the Static Method (Pairing Mode)

If you don't have cloud credentials or prefer to use Bluetooth directly, you can read the token from the machine when it's in pairing mode:

```python
from pylamarzocco import LaMarzoccoBluetoothClient

# Discover available bluetooth devices
bluetooth_devices = await LaMarzoccoBluetoothClient.discover_devices()

if bluetooth_devices:
    # Put your machine in pairing mode first!
    # Then read the token directly from the machine
    ble_token = await LaMarzoccoBluetoothClient.read_token(bluetooth_devices[0])
```

**Note:** This method only works when the machine is in pairing mode. Consult your machine's manual for instructions on how to enable pairing mode.

#### Method 3: Scanning the QR Code

The Bluetooth token is printed as a QR code on a label inside the machine's chassis. You can scan this QR code with a standard QR code reader app to obtain the token string.

1. Open the machine's chassis (consult your machine's manual for instructions)
2. Locate the QR code label
3. Scan the QR code with a QR code reader app
4. The scanned value is your Bluetooth token

### Using the Bluetooth Client

Once you have the token from any of the above methods, you can initialize the Bluetooth client:

```python
from pylamarzocco import LaMarzoccoBluetoothClient

# Discover available bluetooth devices
if bluetooth_devices := await LaMarzoccoBluetoothClient.discover_devices():
    print("Found bluetooth device:", bluetooth_devices[0])
    
    bluetooth_client = LaMarzoccoBluetoothClient(
        ble_device=bluetooth_devices[0],
        ble_token=ble_token,  # Use the token from any of the three methods above
    )
```

## LaMarzoccoMachine

Once you have any or all of the clients, you can initialize a machine object with:

```python
from pylamarzocco import LaMarzoccoMachine

machine = LaMarzoccoMachine(
    serial_number=serial_number,
    cloud_client=cloud_client,
    bluetooth_client=bluetooth_client,  # Optional
)
```

You can then use the machine object to send commands to the machine, or to get the current status of the machine.

### Getting Machine Information

```python
# Get dashboard information
await machine.get_dashboard()

# Get firmware information
await machine.get_firmware()

# Get schedule settings
await machine.get_schedule()

# Get machine settings
await machine.get_settings()

# Get statistics
await machine.get_statistics()

# Get machine data as dictionary
machine_data = machine.to_dict()
```

### Controlling the Machine

```python
from pylamarzocco.const import SteamTargetLevel

# Turn machine on/off
await machine.set_power(True)  # Turn on
await machine.set_power(False)  # Turn off

# Control steam
await machine.set_steam(True)  # Enable steam
await machine.set_steam(False)  # Disable steam

# Set coffee target temperature
await machine.set_coffee_target_temperature(93.0)

# Set steam level (1-3)
await machine.set_steam_level(SteamTargetLevel.LEVEL_2)
```

### WebSockets

The cloud client supports WebSocket connections for real-time updates from the machine dashboard.

To use WebSockets, start the connection with:

```python
from pylamarzocco.models import ThingDashboardWebsocketConfig

def callback(config: ThingDashboardWebsocketConfig):
    """Callback function for websocket updates."""
    print(f"Received update: {config.to_dict()}")

# Connect to dashboard websocket with optional callback
await machine.connect_dashboard_websocket(callback)

# The websocket will receive real-time updates about the machine status
# To disconnect later:
await machine.websocket.disconnect()
```

### Bluetooth Shot Counter

Newer firmware pushes brewing events over Bluetooth in real time. This removes the ~4 s delay of the cloud websocket for shot start/stop.

Requirements:

- an ESP-gateway machine (Linea Micra, Linea Mini, Linea Mini R, GS3 AV/MP) with shot counter firmware; `connect_bluetooth_shot_counter` returns `False` otherwise. `dashboard.shot_counter_supported` tells whether the cloud reports support.
- a Bluetooth client with a valid token
- a free, persistent Bluetooth connection slot (the machine likely accepts only one central at a time)

```python
from pylamarzocco.models import BluetoothMachineTelemetry, BluetoothShotCounterUpdate

def on_shot(update: BluetoothShotCounterUpdate | None):
    """Called on every brewing update, and with None when Bluetooth disconnects."""
    if update is not None:
        print(update.state, update.timer_value, update.brewing_start_time)

def on_telemetry(telemetry: BluetoothMachineTelemetry):
    """Called with the values of each telemetry notification."""
    print(telemetry.steam_boiler_temperature, telemetry.machine_mode)

await machine.get_dashboard()  # or get_dashboard_from_bluetooth()
if await machine.connect_bluetooth_shot_counter(on_shot, on_telemetry):
    ...  # machine.dashboard is now updated in real time

# Later. This doesn't call the callbacks, refresh afterwards if needed.
await machine.disconnect_bluetooth_shot_counter()
```

Brewing states:

- A shot or flush is reported as `Brewing` right away when the machine sends its start event, with a timer of 0. A flush only differs from a shot once it stops.
- When connecting during a shot, `Brewing` follows with the next timer notification.
- `brewing_start_time` is the earliest estimate of the running shot, so late notifications don't move it.
- When subscribing, the machine first replays its last notification, which can be hours old. The first notification of every subscription is discarded.

Telemetry:

- Most notifications carry live machine values: boiler temperatures, the machine mode, and statistics. They never change the brewing state.
- `machine.bluetooth_telemetry` holds the latest values until the shot counter stops or disconnects.
- A machine mode is applied to the `CMMachineStatus` widget right away, for example standby half a second after switching the machine off.

While the shot counter is running:

- The connection stays open and reconnects automatically. Idle disconnects are paused.
- Reconnects back off up to 60 s. They stop after 3 failed logins in a row; `bluetooth_client.authentication_failed` then reports the likely wrong token.
- A single failed command does not drop the connection.
- The `CMMachineStatus` widget is overridden with the Bluetooth state (`status` and `brewing_start_time`), including after later cloud updates.
- If no Bluetooth update arrives for 60 s, the cloud state is used again and the callback receives `None`.
- `machine.last_shot_time` holds the duration of the last shot.
- Bluetooth commands such as `set_power` share the same connection. Requests are serialized, so responses can't mix up.
- Without callbacks, the dashboard websocket `update_callback` is used for brewing updates and machine mode changes.

If the shot counter characteristic is missing, it may be a stale service cache. The cached services are then cleared and rediscovered once before `connect_bluetooth_shot_counter` returns `False`.

For long-running hosts (e.g. Home Assistant with adapters or proxies), pass `ble_device_callback` to `LaMarzoccoBluetoothClient` so reconnects use the most recent `BLEDevice`.

## Complete Example

Here's a complete example of using the library:

```python
import asyncio
import uuid
from pathlib import Path
from aiohttp import ClientSession
from pylamarzocco import LaMarzoccoCloudClient, LaMarzoccoMachine
from pylamarzocco.util import InstallationKey, generate_installation_key

SERIAL = "your_serial_number"
USERNAME = "your_username"
PASSWORD = "your_password"

async def main():
    # Generate or load key material
    key_file = Path("installation_key.json")
    if not key_file.exists():
        installation_key = generate_installation_key(str(uuid.uuid4()).lower())
        with open(key_file, "w", encoding="utf-8") as f:
            f.write(installation_key.to_json())
        registration_required = True
    else:
        with open(key_file, "r", encoding="utf-8") as f:
            installation_key = InstallationKey.from_json(f.read())
        registration_required = False

    async with ClientSession() as session:
        # Initialize cloud client
        client = LaMarzoccoCloudClient(
            username=USERNAME,
            password=PASSWORD,
            installation_key=installation_key,
            client=session,
        )
        
        # Register device if needed
        if registration_required:
            await client.async_register_client()
        
        # Initialize machine
        machine = LaMarzoccoMachine(SERIAL, client)
        
        # Get machine information
        await machine.get_dashboard()
        await machine.get_firmware()
        await machine.get_settings()
        
        # Control the machine
        await machine.set_power(True)
        await asyncio.sleep(5)
        await machine.set_power(False)

asyncio.run(main())
```
