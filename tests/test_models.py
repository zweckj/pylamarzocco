"""Testing models serialization and deserialization."""

from syrupy import SnapshotAssertion
from pylamarzocco.models.config import DashboardWSConfig
from pylamarzocco.models.schedule import SmartWakeUpScheduleWSConfig, SchedulingSettings
from pylamarzocco.models.statistics import Statistics

from .conftest import load_fixture


async def test_device_config(snapshot: SnapshotAssertion) -> None:
    """Test the config model serialization."""

    fixture = load_fixture("machine", "config_micra.json")
    device = DashboardWSConfig.from_dict(fixture)
    assert device.to_dict() == snapshot


async def test_scheduling_config(snapshot: SnapshotAssertion) -> None:
    """Test the config model serialization."""

    fixture = load_fixture("machine", "schedule.json")
    schedule = SchedulingSettings.from_dict(fixture)
    assert schedule.to_dict() == snapshot


async def test_scheduling_websocket_config(snapshot: SnapshotAssertion) -> None:
    """Test the config model serialization."""

    fixture = load_fixture("machine", "schedule_ws.json")
    schedule = SmartWakeUpScheduleWSConfig.from_dict(fixture)
    assert schedule.to_dict() == snapshot


async def test_statistic_config(snapshot: SnapshotAssertion) -> None:
    """Test the config model serialization."""

    fixture = load_fixture("machine", "statistics.json")
    schedule = Statistics.from_dict(fixture)
    assert schedule.to_dict() == snapshot
