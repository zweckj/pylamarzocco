"""Test the LaMarzoccoGrinder class."""

import pytest
from syrupy import SnapshotAssertion

from pylamarzocco.client_cloud import LaMarzoccoCloudClient
from pylamarzocco.const import GrinderModel
from pylamarzocco.lm_grinder import LaMarzoccoGrinder

from . import GRINDER_SERIAL

pytestmark = pytest.mark.asyncio


async def test_create(
    cloud_client: LaMarzoccoCloudClient,
    snapshot: SnapshotAssertion,
) -> None:
    """Test creation of a cloud client."""

    machine = await LaMarzoccoGrinder.create(
        model=GrinderModel("Pico"),
        serial_number=GRINDER_SERIAL,
        name="MyMachine",
        cloud_client=cloud_client,
    )
    assert machine == snapshot
