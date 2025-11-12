"""Testing models serialization and deserialization."""

from syrupy import SnapshotAssertion

from pylamarzocco.const import WidgetType
from pylamarzocco.models import (
    SmartWakeUpScheduleWebsocketConfig,
    ThingDashboardWebsocketConfig,
)
from pylamarzocco.models._general import BaseWidget

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


async def test_unknown_widget_code() -> None:
    """Test that unknown widget codes are handled gracefully."""
    # Test with unknown widget code that's not in the WidgetType enum
    unknown_widget = {"code": "UnknownNewWidget", "index": 1}
    widget = BaseWidget.from_dict(unknown_widget)
    
    # Verify the unknown code is stored as a string
    assert widget.code == "UnknownNewWidget"
    assert isinstance(widget.code, str)
    assert widget.index == 1
    
    # Verify serialization works
    serialized = widget.to_dict()
    assert serialized == unknown_widget


async def test_known_widget_code() -> None:
    """Test that known widget codes are still parsed as enums."""
    # Test with known widget code
    known_widget = {"code": "CMMachineStatus", "index": 1}
    widget = BaseWidget.from_dict(known_widget)
    
    # Verify the known code is stored as enum
    assert widget.code == WidgetType.CM_MACHINE_STATUS
    assert isinstance(widget.code, WidgetType)
    assert widget.index == 1
    
    # Verify serialization works
    serialized = widget.to_dict()
    assert serialized == known_widget


async def test_removed_widgets_with_unknown_codes() -> None:
    """Test that removed widgets with unknown codes are handled correctly."""
    config_data = {
        "connected": True,
        "removedWidgets": [
            {"code": "CMMachineGroupStatus", "index": 1},
            {"code": "UnknownFutureWidget", "index": 2},
            {"code": "CMMachineStatus", "index": 3},
        ],
        "connectionDate": 1742439620235,
        "widgets": [],
        "uuid": "test-uuid",
        "commands": [],
    }
    
    config = ThingDashboardWebsocketConfig.from_dict(config_data)
    
    # Verify all removed widgets are parsed correctly
    assert len(config.removed_widgets) == 3
    
    # First widget - unknown code (string)
    assert config.removed_widgets[0].code == "CMMachineGroupStatus"
    assert isinstance(config.removed_widgets[0].code, str)
    
    # Second widget - unknown code (string)
    assert config.removed_widgets[1].code == "UnknownFutureWidget"
    assert isinstance(config.removed_widgets[1].code, str)
    
    # Third widget - known code (enum)
    assert config.removed_widgets[2].code == WidgetType.CM_MACHINE_STATUS
    assert isinstance(config.removed_widgets[2].code, WidgetType)
