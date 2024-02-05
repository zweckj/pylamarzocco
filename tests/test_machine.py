"""Test the LaMarzoccoMachine class."""

import pytest

from syrupy import SnapshotAssertion

from lmcloud.client_cloud import LaMarzoccoCloudClient
from lmcloud.lm_machine import LaMarzoccoMachine


@pytest.mark.asyncio
async def test_create(
    cloud_client: LaMarzoccoCloudClient,
    snapshot: SnapshotAssertion,
):
    """Test creation of a cloud client."""
    LaMarzoccoMachine.cloud_client = cloud_client

    machine = await LaMarzoccoMachine.create(
        model="GS3",
        serial_number="123456",
        name="MyMachine",
    )
    assert machine == snapshot
