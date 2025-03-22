"""Testing the cloud client."""

from aioresponses import aioresponses
from syrupy import SnapshotAssertion

from pylamarzocco.const import CUSTOMER_APP_URL
from pylamarzocco.clients.cloud import LaMarzoccoCloudClient

from .conftest import load_fixture


async def test_get_thing_dashboard(
    mock_aioresponse: aioresponses, snapshot: SnapshotAssertion
) -> None:
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


async def test_get_thing_settings(
    mock_aioresponse: aioresponses, snapshot: SnapshotAssertion
) -> None:
    """Get a mock response from HTTP request."""

    serial = "MR123456"

    mock_aioresponse.get(
        url=f"{CUSTOMER_APP_URL}/things/{serial}/settings",
        status=200,
        payload=load_fixture("machine", "settings_micra.json"),
    )

    client = LaMarzoccoCloudClient("test", "test")
    result = await client.get_thing_settings(serial)
    assert result.to_dict() == snapshot
