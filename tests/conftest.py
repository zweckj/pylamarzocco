"""Setting up pytest fixtures for the tests."""

import json
from pathlib import Path
from collections.abc import Generator
import pytest
from unittest.mock import patch, AsyncMock
from aioresponses import aioresponses


def load_fixture(device_type: str, file_name: str) -> dict:
    """Load a fixture."""
    with open(
        f"{Path(__file__).parent}/fixtures/{device_type}/{file_name}", encoding="utf-8"
    ) as f:
        return json.load(f)


@pytest.fixture(name="mock_aioresponse")
def fixture_mock_aioresponse() -> Generator[aioresponses, None, None]:
    """Fixture for aioresponses."""
    with aioresponses() as m:
        yield m


@pytest.fixture(autouse=True)
def mock_access_token() -> Generator[AsyncMock]:
    """Mock access token."""
    with patch(
        "pylamarzocco.clients.cloud.LaMarzoccoCloudClient.async_get_access_token"
    ):
        yield AsyncMock(return_value="Token")
