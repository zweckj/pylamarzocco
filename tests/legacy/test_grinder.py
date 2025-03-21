"""Test the LaMarzoccoGrinder class."""

from syrupy import SnapshotAssertion

from pylamarzocco.legacy.clients.cloud import LaMarzoccoCloudClient
from pylamarzocco.legacy.const import GrinderModel
from pylamarzocco.legacy.devices.grinder import LaMarzoccoGrinder

from . import GRINDER_SERIAL


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
