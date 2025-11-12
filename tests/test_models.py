"""Testing models serialization and deserialization."""

import logging

import pytest
from syrupy import SnapshotAssertion

from pylamarzocco.const import WidgetType
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


async def test_removed_widgets_with_unknown_codes(caplog: pytest.LogCaptureFixture) -> None:
    """Test that removed widgets with unknown codes are filtered out and logged."""
    config_data = {
        "connected": True,
        "removedWidgets": [
            {"code": "NewWidget2026", "index": 1},         # Unknown - will be filtered
            {"code": "UnknownFutureWidget", "index": 2},   # Unknown - will be filtered
            {"code": "CMMachineStatus", "index": 3},       # Known - will be kept
        ],
        "connectionDate": 1742439620235,
        "widgets": [],
        "uuid": "test-uuid",
        "commands": [],
    }
    
    with caplog.at_level(logging.WARNING):
        config = ThingDashboardWebsocketConfig.from_dict(config_data)
    
    # Only the known widget should remain
    assert len(config.removed_widgets) == 1
    assert config.removed_widgets[0].code == WidgetType.CM_MACHINE_STATUS
    assert isinstance(config.removed_widgets[0].code, WidgetType)
    
    # Verify warnings were logged for unknown codes
    assert "NewWidget2026" in caplog.text
    assert "UnknownFutureWidget" in caplog.text


async def test_widgets_with_unknown_codes(caplog: pytest.LogCaptureFixture) -> None:
    """Test that active widgets with unknown codes are filtered out and logged."""
    config_data = {
        "connected": True,
        "removedWidgets": [],
        "connectionDate": 1742439620235,
        "widgets": [
            {
                "code": "UnknownWidget",
                "index": 1,
                "output": {"widget_type": "UnknownWidget"},
            },
            {
                "code": "CMMachineStatus",
                "index": 2,
                "output": {
                    "widget_type": "CMMachineStatus",
                    "status": "StandBy",
                    "availableModes": ["BrewingMode", "StandBy"],
                    "mode": "StandBy",
                    "nextStatus": None,
                    "brewingStartTime": None,
                },
            },
        ],
        "uuid": "test-uuid",
        "commands": [],
    }
    
    with caplog.at_level(logging.WARNING):
        config = ThingDashboardWebsocketConfig.from_dict(config_data)
    
    # Only the known widget should remain
    assert len(config.widgets) == 1
    assert config.widgets[0].code == WidgetType.CM_MACHINE_STATUS
    
    # Verify warning was logged for unknown code
    assert "UnknownWidget" in caplog.text
