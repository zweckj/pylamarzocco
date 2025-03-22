"""Testing the cloud client."""

from aioresponses import aioresponses
from pylamarzocco.const import CUSTOMER_APP_URL
from pylamarzocco.clients.cloud import LaMarzoccoCloudClient
from syrupy import SnapshotAssertion

from .conftest import load_fixture


async def test_get_thing_dashboard(mock_aioresponse: aioresponses, snapshot: SnapshotAssertion) -> None:
    """Get a mock response from HTTP request."""

    serial = "MR123456"

    mock_aioresponse.get(
        url=f"{CUSTOMER_APP_URL}/things/{serial}/dashboard",
        status=200,
        payload=load_fixture("machine", "dashboard_micra.json"),
    )

    client = LaMarzoccoCloudClient("test", "test")
    result = await client.get_thing_dashboard(serial)
    assert result.to_dict() == snapshot

