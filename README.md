# La Marzocco Python Client

This is a library to interface with La Marzocco's Home machines.

![workflow](https://github.com/zweckj/pylamarzocco/actions/workflows/pypi.yaml/badge.svg)
[![codecov](https://codecov.io/gh/zweckj/pylamarzocco/graph/badge.svg?token=350GPTLZXS)](https://codecov.io/gh/zweckj/pylamarzocco)

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

To use Bluetooth:

```python
from pylamarzocco import LaMarzoccoBluetoothClient

# Discover available bluetooth devices
if bluetooth_devices := await LaMarzoccoBluetoothClient.discover_devices():
    print("Found bluetooth device:", bluetooth_devices[0])
    
    # Read the token from the machine (only works in pairing mode)
    # Or use a previously saved token
    ble_token = await LaMarzoccoBluetoothClient.read_token(bluetooth_devices[0].address)

    bluetooth_client = LaMarzoccoBluetoothClient(
        ble_device=bluetooth_devices[0],
        ble_token=ble_token,
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
