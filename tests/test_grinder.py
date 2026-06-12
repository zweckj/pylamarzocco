"""Test the grinder module."""

from unittest.mock import MagicMock

import pytest

from pylamarzocco import LaMarzoccoCloudClient, LaMarzoccoGrinder
from pylamarzocco.const import GrinderMode, WidgetType
from pylamarzocco.models import GrinderBaristaLight, GrinderMachineStatus


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


async def test_set_power_updates_mode(
    mock_grinder: LaMarzoccoGrinder,
    mock_cloud_client: MagicMock,
) -> None:
    """Test the set_power method (wake / standby)."""
    mock_grinder.dashboard.config[WidgetType.G_MACHINE_STATUS] = GrinderMachineStatus(
        status=GrinderMode.STANDBY,
        available_modes=[GrinderMode.GRINDING, GrinderMode.STANDBY],
        mode=GrinderMode.STANDBY,
    )

    assert await mock_grinder.set_power(True)
    mock_cloud_client.set_grinder_mode.assert_called_once_with(
        "GR123456", GrinderMode.GRINDING
    )

    status = mock_grinder.dashboard.config[WidgetType.G_MACHINE_STATUS]
    assert isinstance(status, GrinderMachineStatus)
    assert status.mode is GrinderMode.GRINDING


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
