"""Testing models serialization and deserialization."""

import logging

import pytest
from syrupy import SnapshotAssertion

from pylamarzocco.const import WidgetType
from pylamarzocco.models import (
    SmartWakeUpScheduleWebsocketConfig,
    ThingDashboardWebsocketConfig,
)
from pylamarzocco.models._statistics import ThingStatistics

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
    
    # Verify warning was logged for unknown code and includes JSON
    assert "UnknownWidget" in caplog.text
    # Verify that full JSON is logged for dict objects
    assert '"index": 1' in caplog.text


async def test_widget_code_strings_filtering(caplog: pytest.LogCaptureFixture) -> None:
    """Test that widget code strings (not dicts) are filtered properly."""
    stats_data = {
        "serialNumber": "test-serial",
        "selectedWidgetCodes": [
            "CMMachineStatus",     # Known - will be kept
            "UnknownCode1",        # Unknown - will be filtered
            "CMCoffeeBoiler",      # Known - will be kept
            "UnknownCode2",        # Unknown - will be filtered
        ],
        "allWidgetCodes": [
            "CMSteamBoilerLevel",  # Known - will be kept
            "FutureWidget",        # Unknown - will be filtered
        ],
        "selectedWidgets": [],
    }
    
    with caplog.at_level(logging.WARNING):
        stats = ThingStatistics.from_dict(stats_data)
    
    # Only known codes should remain
    assert len(stats.selected_widget_codes) == 2
    assert WidgetType.CM_MACHINE_STATUS in stats.selected_widget_codes
    assert WidgetType.CM_COFFEE_BOILER in stats.selected_widget_codes
    
    assert len(stats.all_widget_codes) == 1
    assert WidgetType.CM_STEAM_BOILER_LEVEL in stats.all_widget_codes
    
    # Verify warnings were logged for unknown codes (strings, not dicts)
    assert "UnknownCode1" in caplog.text
    assert "UnknownCode2" in caplog.text
    assert "FutureWidget" in caplog.text


async def test_mixed_valid_invalid_widgets(caplog: pytest.LogCaptureFixture) -> None:
    """Test handling of mix of valid and invalid widgets."""
    config_data = {
        "connected": True,
        "removedWidgets": [
            {"code": "CMMachineStatus", "index": 1},
            {"code": "InvalidWidget1", "index": 2},
            {"code": "CMCoffeeBoiler", "index": 3},
            {"code": "InvalidWidget2", "index": 4},
            {"code": "CMSteamBoilerLevel", "index": 5},
        ],
        "connectionDate": 1742439620235,
        "widgets": [],
        "uuid": "test-uuid",
        "commands": [],
    }
    
    with caplog.at_level(logging.WARNING):
        config = ThingDashboardWebsocketConfig.from_dict(config_data)
    
    # Should have 3 valid widgets
    assert len(config.removed_widgets) == 3
    assert config.removed_widgets[0].code == WidgetType.CM_MACHINE_STATUS
    assert config.removed_widgets[1].code == WidgetType.CM_COFFEE_BOILER
    assert config.removed_widgets[2].code == WidgetType.CM_STEAM_BOILER_LEVEL
    
    # Verify both invalid widgets were logged with full JSON
    assert "InvalidWidget1" in caplog.text
    assert "InvalidWidget2" in caplog.text
    assert '"index": 2' in caplog.text
    assert '"index": 4' in caplog.text


async def test_empty_widget_lists() -> None:
    """Test that empty widget lists are handled correctly."""
    config_data = {
        "connected": True,
        "removedWidgets": [],
        "connectionDate": 1742439620235,
        "widgets": [],
        "uuid": "test-uuid",
        "commands": [],
    }
    
    config = ThingDashboardWebsocketConfig.from_dict(config_data)
    
    assert len(config.removed_widgets) == 0
    assert len(config.widgets) == 0


async def test_all_widgets_invalid(caplog: pytest.LogCaptureFixture) -> None:
    """Test that when all widgets are invalid, result is empty list."""
    config_data = {
        "connected": True,
        "removedWidgets": [
            {"code": "InvalidWidget1", "index": 1},
            {"code": "InvalidWidget2", "index": 2},
            {"code": "InvalidWidget3", "index": 3},
        ],
        "connectionDate": 1742439620235,
        "widgets": [],
        "uuid": "test-uuid",
        "commands": [],
    }
    
    with caplog.at_level(logging.WARNING):
        config = ThingDashboardWebsocketConfig.from_dict(config_data)
    
    # All widgets should be filtered out
    assert len(config.removed_widgets) == 0
    
    # All three should have been logged
    assert "InvalidWidget1" in caplog.text
    assert "InvalidWidget2" in caplog.text
    assert "InvalidWidget3" in caplog.text
