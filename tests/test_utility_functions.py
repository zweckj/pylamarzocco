"""Test utility functions."""

import pytest
from aiohttp import ClientResponse
from unittest.mock import MagicMock

from pylamarzocco.util import is_success


class TestUtilityFunctions:
    """Test general utility functions."""

    def test_is_success_200(self) -> None:
        """Test is_success with status 200."""
        response = MagicMock(spec=ClientResponse)
        response.status = 200
        
        assert is_success(response) is True

    def test_is_success_201(self) -> None:
        """Test is_success with status 201."""
        response = MagicMock(spec=ClientResponse)
        response.status = 201
        
        assert is_success(response) is True

    def test_is_success_299(self) -> None:
        """Test is_success with status 299."""
        response = MagicMock(spec=ClientResponse)
        response.status = 299
        
        assert is_success(response) is True

    def test_is_success_100(self) -> None:
        """Test is_success with status 100."""
        response = MagicMock(spec=ClientResponse)
        response.status = 100
        
        assert is_success(response) is False

    def test_is_success_300(self) -> None:
        """Test is_success with status 300."""
        response = MagicMock(spec=ClientResponse)
        response.status = 300
        
        assert is_success(response) is False

    def test_is_success_404(self) -> None:
        """Test is_success with status 404."""
        response = MagicMock(spec=ClientResponse)
        response.status = 404
        
        assert is_success(response) is False

    def test_is_success_500(self) -> None:
        """Test is_success with status 500."""
        response = MagicMock(spec=ClientResponse)
        response.status = 500
        
        assert is_success(response) is False

    def test_is_success_boundary_199(self) -> None:
        """Test is_success with status 199 (boundary)."""
        response = MagicMock(spec=ClientResponse)
        response.status = 199
        
        assert is_success(response) is False