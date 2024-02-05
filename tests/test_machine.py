"""Test the LaMarzoccoMachine class."""

from unittest.mock import AsyncMock, patch

import pytest
from syrupy import SnapshotAssertion

from lmcloud.client_cloud import LaMarzoccoCloudClient
from lmcloud.const import LaMarzoccoBoilerType, WeekDay
from lmcloud.lm_machine import LaMarzoccoMachine

from . import init_machine, MACHINE_SERIAL

pytestmark = pytest.mark.asyncio


async def test_create(
    cloud_client: LaMarzoccoCloudClient,
    snapshot: SnapshotAssertion,
) -> None:
    """Test creation of a cloud client."""

    machine = await LaMarzoccoMachine.create(
        model="GS3",
        serial_number=MACHINE_SERIAL,
        name="MyMachine",
        cloud_client=cloud_client,
    )
    assert machine == snapshot


async def test_set_temp(
    cloud_client: LaMarzoccoCloudClient,
) -> None:
    """Test setting boiler temperature."""
    machine = await init_machine(cloud_client)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        result = await machine.set_temp(
            LaMarzoccoBoilerType.STEAM,
            120,
        )
    assert result is True
    assert machine.boilers[LaMarzoccoBoilerType.STEAM].target_temperature == 120


async def test_set_prebrew_infusion(
    cloud_client: LaMarzoccoCloudClient,
) -> None:
    """Test setting prebrew infusion."""
    machine = await init_machine(cloud_client)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        result = await machine.set_prebrew_time(
            1.0,
            3.5,
        )
        assert result is True
        assert machine.prebrew_configuration[1].on_time == 1.0
        assert machine.prebrew_configuration[1].off_time == 3.5

        result = await machine.set_preinfusion_time(4.5)
        assert result is True
        assert machine.prebrew_configuration[1].off_time == 4.5


async def test_set_schedule(
    cloud_client: LaMarzoccoCloudClient,
) -> None:
    """Test setting prebrew infusion."""
    machine = await init_machine(cloud_client)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        result = await machine.set_schedule_day(
            day=WeekDay.MONDAY,
            enabled=True,
            h_on=3,
            m_on=0,
            h_off=24,
            m_off=0,
        )
    assert result is True
