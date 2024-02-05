"""Fixtures for the tests."""

import json
from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch, AsyncMock

import pytest
from httpx import Response

from lmcloud.client_cloud import LaMarzoccoCloudClient


@pytest.fixture
def cloud_client() -> Generator[LaMarzoccoCloudClient, None, None]:
    """Fixture for a cloud client."""

    client = LaMarzoccoCloudClient("username", "password")
    with open(f"{Path(__file__).parent}/fixtures/config.json", encoding="utf-8") as f:
        data = json.load(f)

    oauth_client = AsyncMock()
    oauth_client.request.return_value = Response(status_code=200, json=data)

    client._oauth_client = oauth_client
    yield client
