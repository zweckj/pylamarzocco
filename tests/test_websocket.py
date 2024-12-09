""""Test websocket messages parsing."""

from dataclasses import asdict

from syrupy import SnapshotAssertion

from pylamarzocco.devices.machine import LaMarzoccoMachine

from pylamarzocco.const import PhysicalKey


async def test_websocket_message(
    machine: LaMarzoccoMachine,
    snapshot: SnapshotAssertion,
):
    """Test parsing of websocket messages."""

    message = r'[{"Boilers":"[{\"id\":\"SteamBoiler\",\"isEnabled\":true,\"target\":131,\"current\":113},{\"id\":\"CoffeeBoiler1\",\"isEnabled\":true,\"target\":94,\"current\":81}]"}]'
    machine.on_websocket_message_received(message)
    assert asdict(machine.config) == snapshot

    message = r'[{"BoilersTargetTemperature":"{\"SteamBoiler\":131,\"CoffeeBoiler1\":94}"},{"Boilers":"[{\"id\":\"SteamBoiler\",\"isEnabled\":true,\"target\":131,\"current\":50},{\"id\":\"CoffeeBoiler1\",\"isEnabled\":true,\"target\":94,\"current\":36}]"}]'
    machine.on_websocket_message_received(message)
    assert asdict(machine.config) == snapshot


async def test_group_capabilities_websocket_message(
    machine: LaMarzoccoMachine,
):
    """Test parsing of group capabilities websocket message."""
    msg = '[{"GroupCapabilities": "[{\\"capabilities\\":{\\"groupType\\":\\"AV_Group\\",\\"groupNumber\\":\\"Group1\\",\\"boilerId\\":\\"CoffeeBoiler1\\",\\"hasScale\\":false,\\"hasFlowmeter\\":true,\\"numberOfDoses\\":4},\\"doses\\":[{\\"groupNumber\\":\\"Group1\\",\\"doseIndex\\":\\"DoseA\\",\\"doseType\\":\\"PulsesType\\",\\"stopTarget\\":126},{\\"groupNumber\\":\\"Group1\\",\\"doseIndex\\":\\"DoseB\\",\\"doseType\\":\\"PulsesType\\",\\"stopTarget\\":130},{\\"groupNumber\\":\\"Group1\\",\\"doseIndex\\":\\"DoseC\\",\\"doseType\\":\\"PulsesType\\",\\"stopTarget\\":140},{\\"groupNumber\\":\\"Group1\\",\\"doseIndex\\":\\"DoseD\\",\\"doseType\\":\\"PulsesType\\",\\"stopTarget\\":77}],\\"doseMode\\":{\\"groupNumber\\":\\"Group1\\",\\"brewingType\\":\\"PulsesType\\"}}]"}]'
    machine.on_websocket_message_received(msg)
    assert machine.config.doses[PhysicalKey(1)] == 126
    assert machine.config.doses[PhysicalKey(2)] == 130
    assert machine.config.doses[PhysicalKey(3)] == 140
    assert machine.config.doses[PhysicalKey(4)] == 77


async def test_flush_snapshot_message(machine: LaMarzoccoMachine):
    """Test the flush snapshot message"""
    machine.config.brew_active = True
    msg = r'[{"FlushSnapshotGroup1": "{\"groupConfiguration\":{\"groupNumber\":\"Group1\",\"capabilities\":{\"groupType\":\"AV_Group\",\"boilerId\":\"CoffeeBoiler1\",\"boilerTemperature\":97,\"boilerTemperatureAtStart\":97,\"hasScale\":false,\"hasFlowmeter\":true},\"dose\":{\"doseIndex\":\"DoseA\",\"stopTarget\":0,\"doseType\":\"PulsesType\"},\"doseMode\":{\"brewingType\":\"PulsesType\"}},\"flushInfo\":{\"doseIndex\":\"DoseA\",\"stopReason\":\"Manual\",\"time\":4.521,\"stopType\":\"Volumetric\",\"volume\":0}}"},{ "FlushStoppedGroup1DoseIndex": "DoseA" },{ "FlushStoppedGroup1Time": 4.521 },{ "FlushStoppedGroup1Volume": 0 }]'
    machine.on_websocket_message_received(msg)
    assert not machine.config.brew_active
    assert machine.config.brew_active_duration == 4.521
