"""Test the grinder module."""

from unittest.mock import MagicMock

import pytest

from pylamarzocco import LaMarzoccoCloudClient, LaMarzoccoGrinder
from pylamarzocco.const import (
    DoseIndex,
    GrinderDoseMode,
    GrinderGrindWithMode,
    GrinderSpeedLevelType,
    WidgetType,
)
from pylamarzocco.models import (
    GrinderBaristaLight,
    GrinderDoses,
    GrinderDoseSettings,
    GrinderDosesSettings,
    GrinderGrindWith,
    GrinderMoreDose,
    GrinderSpeed,
    GrinderSpeedLevel,
    GrinderSpeedLevelSetting,
)


@pytest.fixture(name="mock_cloud_client")
def mock_lm_cloud_client() -> MagicMock:
    """Mock the LaMarzoccoCloudClient."""
    client = MagicMock(spec=LaMarzoccoCloudClient)
    return client


@pytest.fixture(name="mock_grinder")
def mock_lm_grinder(
    mock_cloud_client: MagicMock,
) -> LaMarzoccoGrinder:
    """Mock the LaMarzoccoGrinder."""
    grinder = LaMarzoccoGrinder(
        serial_number="GR123456",
        cloud_client=mock_cloud_client,
    )
    return grinder


async def test_set_barista_light(
    mock_grinder: LaMarzoccoGrinder,
    mock_cloud_client: MagicMock,
) -> None:
    """Test the set_barista_light method."""
    mock_grinder.dashboard.config[WidgetType.G_BARISTA_LIGHT] = GrinderBaristaLight(
        enabled=False
    )

    assert await mock_grinder.set_barista_light(True)
    mock_cloud_client.set_grinder_barista_light.assert_called_once_with(
        "GR123456", True
    )

    barista_light = mock_grinder.dashboard.config[WidgetType.G_BARISTA_LIGHT]
    assert isinstance(barista_light, GrinderBaristaLight)
    assert barista_light.enabled is True


async def test_set_grind_with(
    mock_grinder: LaMarzoccoGrinder,
    mock_cloud_client: MagicMock,
) -> None:
    """Test the set_grind_with method."""
    mock_grinder.dashboard.config[WidgetType.G_GRIND_WITH] = GrinderGrindWith(
        mode=GrinderGrindWithMode.PORTAFILTER
    )

    assert await mock_grinder.set_grind_with(GrinderGrindWithMode.BY_BUTTON)
    mock_cloud_client.set_grinder_grind_with.assert_called_once_with(
        "GR123456", GrinderGrindWithMode.BY_BUTTON
    )

    grind_with = mock_grinder.dashboard.config[WidgetType.G_GRIND_WITH]
    assert isinstance(grind_with, GrinderGrindWith)
    assert grind_with.mode is GrinderGrindWithMode.BY_BUTTON


async def test_set_dose(
    mock_grinder: LaMarzoccoGrinder,
    mock_cloud_client: MagicMock,
) -> None:
    """Test the set_dose method, including the speed level."""
    mock_grinder.dashboard.config[WidgetType.G_DOSES] = GrinderDoses(
        mode=GrinderDoseMode.REV,
        doses=GrinderDosesSettings(
            rev_type=[
                GrinderDoseSettings(
                    dose_index=DoseIndex.DOSE_A,
                    dose=9.5,
                    dose_min=0,
                    dose_max=50,
                    dose_step=0.1,
                ),
            ],
        ),
        speed_levels_supported=True,
        speed_levels=[
            GrinderSpeedLevelSetting(
                dose_index=DoseIndex.DOSE_A,
                level=GrinderSpeedLevelType.LOW,
            ),
        ],
    )
    mock_grinder.dashboard.config[WidgetType.G_SPEED] = GrinderSpeed(
        doses={
            "DoseA": GrinderSpeedLevel(
                level=GrinderSpeedLevelType.LOW,
                auto_enabled=False,
                group_index=None,
            ),
        },
        groups_number=1,
        speed_auto_supported=False,
    )

    assert await mock_grinder.set_dose(
        DoseIndex.DOSE_A,
        12.0,
        speed_level=GrinderSpeedLevelType.HIGH,
    )
    mock_cloud_client.set_grinder_dose.assert_called_once_with(
        "GR123456",
        DoseIndex.DOSE_A,
        12.0,
        GrinderDoseMode.REV,
        GrinderSpeedLevelType.HIGH,
    )

    doses = mock_grinder.dashboard.config[WidgetType.G_DOSES]
    assert isinstance(doses, GrinderDoses)
    assert doses.doses.rev_type[0].dose == 12.0
    assert doses.speed_levels is not None
    assert doses.speed_levels[0].level is GrinderSpeedLevelType.HIGH

    speed = mock_grinder.dashboard.config[WidgetType.G_SPEED]
    assert isinstance(speed, GrinderSpeed)
    assert speed.doses["DoseA"].level is GrinderSpeedLevelType.HIGH


async def test_set_more_dose(
    mock_grinder: LaMarzoccoGrinder,
    mock_cloud_client: MagicMock,
) -> None:
    """Test the set_more_dose method."""
    mock_grinder.dashboard.config[WidgetType.G_MORE_DOSE] = GrinderMoreDose(
        revolutions=1.0,
        revolutions_min=0,
        revolutions_max=5,
        revolutions_step=0.1,
    )

    assert await mock_grinder.set_more_dose(2.5)
    mock_cloud_client.set_grinder_more_dose.assert_called_once_with(
        "GR123456", 2.5
    )

    more_dose = mock_grinder.dashboard.config[WidgetType.G_MORE_DOSE]
    assert isinstance(more_dose, GrinderMoreDose)
    assert more_dose.revolutions == 2.5
