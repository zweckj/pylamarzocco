"""Additional tests for model classes."""

from datetime import datetime, timezone
from pylamarzocco.models._statistics import LastCoffee, ThingStatistics
from pylamarzocco.models._schedule import WakeUpScheduleSettings
from pylamarzocco.const import DoseMode, DoseIndex, WeekDay, WidgetType


class TestLastCoffee:
    """Test LastCoffee model."""

    def test_last_coffee_serialization(self) -> None:
        """Test LastCoffee serialization and deserialization."""
        # Test with timestamp conversion
        data = {
            "time": 1640995200000,  # 2022-01-01 00:00:00 UTC in milliseconds
            "extractionSeconds": 25.5,
            "doseMode": "Dose1",
            "doseIndex": "DoseA",
            "doseValueNumerator": "18.5"
        }
        
        coffee = LastCoffee.from_dict(data)
        
        # Check timestamp conversion
        expected_time = datetime.fromtimestamp(1640995200, tz=timezone.utc)
        assert coffee.time == expected_time
        assert coffee.extraction_seconds == 25.5
        assert coffee.dose_mode == DoseMode.DOSE_1
        assert coffee.dose_index == DoseIndex.DOSE_A
        assert coffee.dose_value_numerator == "18.5"

    def test_last_coffee_with_none_dose_value(self) -> None:
        """Test LastCoffee with None dose value numerator."""
        data = {
            "time": 1640995200000,
            "extractionSeconds": 30.0,
            "doseMode": "Dose2",
            "doseIndex": "ByGroup",
            "doseValueNumerator": None
        }
        
        coffee = LastCoffee.from_dict(data)
        
        assert coffee.dose_value_numerator is None
        assert coffee.dose_mode == DoseMode.DOSE_2
        assert coffee.dose_index == DoseIndex.BY_GROUP

    def test_last_coffee_timestamp_conversion(self) -> None:
        """Test timestamp conversion from milliseconds to datetime."""
        # Different timestamps to test conversion
        timestamps = [
            (0, datetime(1970, 1, 1, tzinfo=timezone.utc)),
            (1609459200000, datetime(2021, 1, 1, tzinfo=timezone.utc)),
            (1672531200000, datetime(2023, 1, 1, tzinfo=timezone.utc)),
        ]
        
        for timestamp_ms, expected_datetime in timestamps:
            data = {
                "time": timestamp_ms,
                "extractionSeconds": 25.0,
                "doseMode": "Dose1",
                "doseIndex": "DoseA"
            }
            
            coffee = LastCoffee.from_dict(data)
            assert coffee.time == expected_datetime


class TestWakeUpScheduleSettings:
    """Test WakeUpScheduleSettings model."""

    def test_basic_schedule_creation(self) -> None:
        """Test basic schedule creation."""
        schedule = WakeUpScheduleSettings(
            on_time_minutes=480,  # 8:00 AM
            off_time_minutes=1320,  # 10:00 PM
            steam_boiler=True
        )
        
        assert schedule.on_time_minutes == 480
        assert schedule.off_time_minutes == 1320
        assert schedule.steam_boiler is True
        assert schedule.enabled is False  # Default value
        assert schedule.identifier is None  # Default value

    def test_schedule_with_all_days(self) -> None:
        """Test schedule covering all days of week."""
        # Test that all WeekDay enum values are available
        all_days = [
            WeekDay.MONDAY,
            WeekDay.TUESDAY, 
            WeekDay.WEDNESDAY,
            WeekDay.THURSDAY,
            WeekDay.FRIDAY,
            WeekDay.SATURDAY,
            WeekDay.SUNDAY
        ]
        
        # Should be able to reference all days without error
        assert len(all_days) == 7
        for day in all_days:
            assert isinstance(day, WeekDay)
            assert isinstance(day.value, str)


class TestThingStatistics:
    """Test ThingStatistics model methods."""

    def test_pre_deserialize_widget_type_assignment(self) -> None:
        """Test __pre_deserialize__ assigns widget_type correctly."""
        # Mock data structure
        data = {
            "selectedWidgets": [
                {
                    "code": "CMMachineStatus",
                    "output": {
                        "status": "On"
                    }
                },
                {
                    "code": "CMCoffeeBoiler", 
                    "output": {
                        "temperature": 92.5
                    }
                }
            ]
        }
        
        # Call pre-deserialize
        result = ThingStatistics.__pre_deserialize__(data)
        
        # Check that widget_type was added to each output
        widgets = result["selectedWidgets"]
        assert widgets[0]["output"]["widget_type"] == "CMMachineStatus"
        assert widgets[1]["output"]["widget_type"] == "CMCoffeeBoiler"
        
        # Original data should be preserved
        assert widgets[0]["output"]["status"] == "On"
        assert widgets[1]["output"]["temperature"] == 92.5

    def test_post_deserialize_widgets_dict_creation(self) -> None:
        """Test __post_deserialize__ creates widgets dict correctly."""
        # Create a minimal ThingStatistics object
        stats = ThingStatistics(serial_number="test")
        
        # Mock selected_widgets data
        from pylamarzocco.models._statistics import Widget, BaseWidgetOutput
        from unittest.mock import MagicMock
        
        widget1 = MagicMock()
        widget1.code = WidgetType.CM_MACHINE_STATUS
        widget1.output = MagicMock(spec=BaseWidgetOutput)
        
        widget2 = MagicMock()
        widget2.code = WidgetType.CM_COFFEE_BOILER
        widget2.output = MagicMock(spec=BaseWidgetOutput)
        
        stats.selected_widgets = [widget1, widget2]
        
        # Call post-deserialize
        result = ThingStatistics.__post_deserialize__(stats)
        
        # Check widgets dict was created correctly
        assert len(result.widgets) == 2
        assert result.widgets[WidgetType.CM_MACHINE_STATUS] == widget1.output
        assert result.widgets[WidgetType.CM_COFFEE_BOILER] == widget2.output

    def test_statistics_default_values(self) -> None:
        """Test ThingStatistics default field values."""
        stats = ThingStatistics(serial_number="defaults-test")
        
        # Test default factory fields
        assert isinstance(stats.selected_widget_codes, list)
        assert len(stats.selected_widget_codes) == 0
        
        assert isinstance(stats.all_widget_codes, list)
        assert len(stats.all_widget_codes) == 0
        
        assert isinstance(stats.selected_widgets, list)
        assert len(stats.selected_widgets) == 0
        
        assert isinstance(stats.widgets, dict)
        assert len(stats.widgets) == 0
        
        # Test optional field
        assert stats.firmwares is None