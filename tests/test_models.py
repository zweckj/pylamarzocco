"""Testing models serialization and deserialization."""

from syrupy import SnapshotAssertion

from pylamarzocco.models import (
    SmartWakeUpScheduleWebsocketConfig,
    ThingDashboardWebsocketConfig,
)

from .conftest import load_fixture


async def test_device_config(snapshot: SnapshotAssertion) -> None:
    """Test the config model serialization."""

    fixture = load_fixture("machine", "config_micra.json")
    device = ThingDashboardWebsocketConfig.from_dict(fixture)
    assert device.to_dict() == snapshot


async def test_scheduling_websocket_config(snapshot: SnapshotAssertion) -> None:
    """Test the config model serialization."""

    fixture = load_fixture("machine", "schedule_ws.json")
    schedule = SmartWakeUpScheduleWebsocketConfig.from_dict(fixture)
    assert schedule.to_dict() == snapshot
