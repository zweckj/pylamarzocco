"""Setting up pytest fixtures for the tests."""

import json
from collections.abc import Generator
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from aioresponses import aioresponses

from pylamarzocco.const import CUSTOMER_APP_URL


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
def mock_access_token(mock_aioresponse: aioresponses) -> Generator[AsyncMock]:
    """Mock access getting token."""
    mock_aioresponse.post(
        url=f"{CUSTOMER_APP_URL}/auth/signin",
        status=200,
        payload={
            "accessToken": "mock-access",
            "refreshToken": "mock-refresh",
        },
        repeat=True,
    )
    yield AsyncMock()


@pytest.fixture(name="serial")
def mock_serial() -> str:
    return "MR123456"
