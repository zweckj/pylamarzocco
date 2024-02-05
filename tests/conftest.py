"""Fixtures for the tests."""

import json
from collections.abc import Generator
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from httpx import Response
from http import HTTPMethod

from lmcloud.client_cloud import LaMarzoccoCloudClient


@pytest.fixture
def cloud_client() -> Generator[LaMarzoccoCloudClient, None, None]:
    """Fixture for a cloud client."""

    client = LaMarzoccoCloudClient("username", "password")

    def get_mock_response(*args, **kwargs) -> Response:
        fixture_path = f"{Path(__file__).parent}/fixtures/"
        method: HTTPMethod = args[0]
        url: str = str(args[1])
        file_name = "config.json"

        if "firmware" in url:
            file_name = "firmware.json"
        elif "counters" in url:
            file_name = "counters.json"

        with open(fixture_path + file_name, encoding="utf-8") as f:
            data = json.load(f)
        if method == HTTPMethod.GET:
            return Response(200, json=data)
        return Response(204)

    oauth_client = AsyncMock()
    oauth_client.request.side_effect = get_mock_response

    client._oauth_client = oauth_client  # pylint: disable=protected-access
    yield client
