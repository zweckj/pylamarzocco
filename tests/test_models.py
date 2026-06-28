"""Testing models serialization and deserialization."""

import logging

import pytest
from syrupy import SnapshotAssertion

from pylamarzocco.const import DoseMode, FirmwareType, WidgetType
from pylamarzocco.models import (
    AutoOnOff,
    BrewingPressureSettings,
    EcoMode,
    GroupDosesSettings,
    HotWaterDose,
    ProfileSettings,
    RinseFlush,
    ThingDashboardConfig,
    ThingDashboardWebsocketConfig,
    ThingSchedulingSettings,
    ThingSettings,
)
from pylamarzocco.models._statistics import ThingStatistics

from .conftest import load_fixture


async def test_device_config(snapshot: SnapshotAssertion) -> None:
    """Test the config model serialization."""

    fixture = load_fixture("machine", "config_micra.json")
    device = ThingDashboardWebsocketConfig.from_dict(fixture)
    assert device.to_dict() == snapshot


async def test_strada_settings_with_file_firmware() -> None:
    """Strada X settings parse with the additional 'File' firmware type."""

    fixture = load_fixture("machine", "settings_strada.json")
    settings = ThingSettings.from_dict(fixture)
    assert FirmwareType.FILE in settings.firmwares
    file_fw = settings.firmwares[FirmwareType.FILE]
    assert file_fw.build_version == "v17"
    assert file_fw.change_log is None


async def test_strada_schedule_eco_mode_and_auto_on_off() -> None:
    """Strada X schedule parses null smartWakeUpSleep and the eco mode objects."""

    fixture = load_fixture("machine", "schedule_strada.json")
    schedule = ThingSchedulingSettings.from_dict(fixture)

    assert schedule.smart_wake_up_sleep is None

    assert isinstance(schedule.auto_on_off, AutoOnOff)
    assert schedule.auto_on_off.on_time_minutes == 360
    assert schedule.auto_on_off.off_time_minutes == 1080
    assert isinstance(schedule.auto_on_off.eco_mode, EcoMode)

    assert schedule.eco_mode_supported is True
    assert isinstance(schedule.eco_mode, EcoMode)
    assert schedule.eco_mode.offset == 10
    assert schedule.eco_mode.timeout_minutes == 120


async def test_schedule_auto_on_off_string() -> None:
    """Schedule with a string autoOnOff (e.g. Linea Micra) still parses."""

    fixture = load_fixture("machine", "schedule.json")
    schedule = ThingSchedulingSettings.from_dict(fixture)
    assert schedule.auto_on_off == "00:30"


async def test_strada_dashboard_group_doses() -> None:
    """Strada X dashboard parses MassType/BrewRatioType doses and pressure object."""

    fixture = load_fixture("machine", "dashboard_strada.json")
    dashboard = ThingDashboardConfig.from_dict(fixture)

    group_doses = dashboard.config[WidgetType.CM_GROUP_DOSES]
    assert isinstance(group_doses, GroupDosesSettings)
    assert group_doses.mode is DoseMode.MASS_TYPE
    assert DoseMode.BREW_RATIO_TYPE in group_doses.available_modes
    assert len(group_doses.doses.mass_type) == 4
    assert len(group_doses.doses.brew_ratio_type) == 4
    assert len(group_doses.doses.pulses_type) == 4

    assert isinstance(group_doses.brewing_pressure, BrewingPressureSettings)
    assert group_doses.brewing_pressure.pressure == 9
    assert group_doses.brewing_pressure.pressure_max == 12

    hot_water = dashboard.config[WidgetType.CM_HOT_WATER_DOSE]
    assert isinstance(hot_water, HotWaterDose)
    assert len(hot_water.doses) == 2
    assert hot_water.doses[0].dose == 8.33

    rinse_flush = dashboard.config[WidgetType.CM_RINSE_FLUSH]
    assert isinstance(rinse_flush, RinseFlush)
    assert rinse_flush.time_seconds == 3.0


async def test_strada_dashboard_profile_mode() -> None:
    """Strada X dashboard parses the ProfileType mode with graph data."""

    fixture = load_fixture("machine", "dashboard_strada_profile.json")
    dashboard = ThingDashboardConfig.from_dict(fixture)

    group_doses = dashboard.config[WidgetType.CM_GROUP_DOSES]
    assert isinstance(group_doses, GroupDosesSettings)
    assert group_doses.mode is DoseMode.PROFILE_TYPE
    assert DoseMode.PROFILE_TYPE in group_doses.available_modes

    assert isinstance(group_doses.profile, ProfileSettings)
    assert group_doses.profile.selected_profile == 15
    assert group_doses.profile.number_of_profiles == 15
    assert group_doses.profile.mass == 47.5
    assert group_doses.profile.time == 32.1
    assert group_doses.profile.graph is not None
    assert len(group_doses.profile.graph.x) == 300
    assert len(group_doses.profile.graph.y) == 300

    assert dashboard.to_dict()


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
