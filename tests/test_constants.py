"""Test constants and enums."""

from pylamarzocco.const import (
    BASE_URL,
    CUSTOMER_APP_URL,
    MachineMode,
    MachineState,
    PreExtractionMode,
    WidgetType,
    StompMessageType,
    DeviceType,
    ModelCode,
    ModelName,
    BoilerType,
    WeekDay,
    DoseIndex,
    DoseMode,
    SmartStandByType,
    SteamTargetLevel,
    CommandStatus,
)


class TestConstants:
    """Test constant values and enums."""

    def test_base_url_constant(self) -> None:
        """Test BASE_URL constant."""
        assert BASE_URL == "lion.lamarzocco.io"

    def test_customer_app_url_constant(self) -> None:
        """Test CUSTOMER_APP_URL constant."""
        assert CUSTOMER_APP_URL == "https://lion.lamarzocco.io/api/customer-app"

    def test_machine_mode_enum(self) -> None:
        """Test MachineMode enum values."""
        assert MachineMode.BREWING_MODE == "BrewingMode"
        assert MachineMode.ECO_MODE == "EcoMode"
        assert MachineMode.STANDBY == "StandBy"

    def test_machine_state_enum(self) -> None:
        """Test MachineState enum values."""
        assert MachineState.STANDBY == "StandBy"
        assert MachineState.POWERED_ON == "PoweredOn"
        assert MachineState.BREWING == "Brewing"
        assert MachineState.OFF == "Off"

    def test_pre_extraction_mode_enum(self) -> None:
        """Test PreExtractionMode enum values."""
        assert PreExtractionMode.PREINFUSION == "PreInfusion"
        assert PreExtractionMode.PREBREWING == "PreBrewing"
        assert PreExtractionMode.DISABLED == "Disabled"

    def test_widget_type_enum(self) -> None:
        """Test WidgetType enum values."""
        assert WidgetType.CM_MACHINE_STATUS == "CMMachineStatus"
        assert WidgetType.CM_COFFEE_BOILER == "CMCoffeeBoiler"
        assert WidgetType.CM_STEAM_BOILER_LEVEL == "CMSteamBoilerLevel"
        assert WidgetType.CM_PRE_EXTRACTION == "CMPreExtraction"
        assert WidgetType.CM_PRE_BREWING == "CMPreBrewing"
        assert WidgetType.CM_BACK_FLUSH == "CMBackFlush"

    def test_stomp_message_type_enum(self) -> None:
        """Test StompMessageType enum values."""
        assert StompMessageType.CONNECT == "CONNECT"
        assert StompMessageType.CONNECTED == "CONNECTED"
        assert StompMessageType.SUBSCRIBE == "SUBSCRIBE"
        assert StompMessageType.UNSUBSCRIBE == "UNSUBSCRIBE"
        assert StompMessageType.MESSAGE == "MESSAGE"
        assert StompMessageType.ERROR == "ERROR"

    def test_device_type_enum(self) -> None:
        """Test DeviceType enum values."""
        assert DeviceType.MACHINE == "CoffeeMachine"
        assert DeviceType.GRINDER == "Grinder"

    def test_model_code_enum(self) -> None:
        """Test ModelCode enum values."""
        assert ModelCode.GS3 == "GS3"
        assert ModelCode.GS3_AV == "GS3AV"
        assert ModelCode.GS3_MP == "GS3MP"
        assert ModelCode.LINEA_MICRA == "LINEAMICRA"
        assert ModelCode.LINEA_MINI == "LINEAMINI"
        assert ModelCode.LINEA_MINI_R == "LINEAMINIR"

    def test_model_name_enum(self) -> None:
        """Test ModelName enum values."""
        assert ModelName.GS3 == "GS3"
        assert ModelName.GS3_AV == "GS3 AV"
        assert ModelName.GS3_MP == "GS3 MP"
        assert ModelName.LINEA_MICRA == "Linea Micra"
        assert ModelName.LINEA_MINI == "Linea Mini"
        assert ModelName.LINEA_MINI_R == "Linea Mini R"

    def test_boiler_type_enum(self) -> None:
        """Test BoilerType enum values."""
        assert BoilerType.COFFEE == "CoffeeBoiler1"
        assert BoilerType.STEAM == "SteamBoiler"

    def test_week_day_enum(self) -> None:
        """Test WeekDay enum values."""
        assert WeekDay.MONDAY == "Monday"
        assert WeekDay.TUESDAY == "Tuesday"
        assert WeekDay.WEDNESDAY == "Wednesday"
        assert WeekDay.THURSDAY == "Thursday"
        assert WeekDay.FRIDAY == "Friday"
        assert WeekDay.SATURDAY == "Saturday"
        assert WeekDay.SUNDAY == "Sunday"

    def test_dose_index_enum(self) -> None:
        """Test DoseIndex enum values."""
        assert DoseIndex.DOSE_A == "DoseA"
        assert DoseIndex.DOSE_B == "DoseB"
        assert DoseIndex.DOSE_C == "DoseC"
        assert DoseIndex.DOSE_D == "DoseD"
        assert DoseIndex.BY_GROUP == "ByGroup"
        assert DoseIndex.CONTINUOUS == "Continuous"

    def test_dose_mode_enum(self) -> None:
        """Test DoseMode enum values."""
        assert DoseMode.DOSE_1 == "Dose1"
        assert DoseMode.DOSE_2 == "Dose2"
        assert DoseMode.CONTINUOUS == "Continuous"
        assert DoseMode.PULSES_TYPE == "PulsesType"

    def test_smart_standby_type_enum(self) -> None:
        """Test SmartStandByType enum values."""
        assert SmartStandByType.LAST_BREW == "LastBrewing"
        assert SmartStandByType.POWER_ON == "PowerOn"

    def test_steam_target_level_enum(self) -> None:
        """Test SteamTargetLevel enum values."""
        assert SteamTargetLevel.LEVEL_1 == "Level1"
        assert SteamTargetLevel.LEVEL_2 == "Level2"
        assert SteamTargetLevel.LEVEL_3 == "Level3"

    def test_command_status_enum(self) -> None:
        """Test CommandStatus enum values."""
        assert CommandStatus.PENDING == "Pending"
        assert CommandStatus.SUCCESS == "Success"
        assert CommandStatus.ERROR == "Error"
        assert CommandStatus.IN_PROGRESS == "InProgress"
        assert CommandStatus.TIMEOUT == "Timeout"

    def test_enum_string_behavior(self) -> None:
        """Test that enums behave as strings."""
        # Test that enum values can be used as strings
        assert str(MachineMode.BREWING_MODE) == "BrewingMode"
        assert str(ModelCode.LINEA_MICRA) == "LINEAMICRA"
        
        # Test string operations work
        assert MachineMode.BREWING_MODE.lower() == "brewingmode"
        assert MachineMode.BREWING_MODE.startswith("Brewing")
        
    def test_enum_comparison(self) -> None:
        """Test enum comparison operations."""
        # Test equality
        assert MachineMode.BREWING_MODE == "BrewingMode"
        assert MachineMode.BREWING_MODE != "EcoMode"
        
        # Test in collections
        modes = [MachineMode.BREWING_MODE, MachineMode.ECO_MODE]
        assert MachineMode.BREWING_MODE in modes
        assert MachineMode.STANDBY not in modes

    def test_enum_completeness(self) -> None:
        """Test that enum classes have expected number of values."""
        # Test a few key enums have reasonable number of values
        assert len(list(MachineMode)) >= 3
        assert len(list(StompMessageType)) >= 6
        assert len(list(WeekDay)) == 7
        assert len(list(ModelCode)) >= 6