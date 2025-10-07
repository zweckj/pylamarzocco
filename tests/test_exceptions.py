"""Test exception classes."""

import pytest

from pylamarzocco.exceptions import (
    AuthFail,
    BluetoothConnectionFailed,
    CloudOnlyFunctionality,
    LaMarzoccoError,
    RequestNotSuccessful,
    UnknownWebSocketMessage,
    UnsupportedModel,
)


class TestExceptions:
    """Test exception classes."""

    def test_lamarzocco_error_base(self) -> None:
        """Test LaMarzoccoError base exception."""
        exc = LaMarzoccoError("test message")
        assert str(exc) == "test message"
        assert isinstance(exc, Exception)

    def test_auth_fail(self) -> None:
        """Test AuthFail exception."""
        exc = AuthFail("Invalid credentials")
        assert str(exc) == "Invalid credentials"
        assert isinstance(exc, LaMarzoccoError)

    def test_request_not_successful(self) -> None:
        """Test RequestNotSuccessful exception."""
        exc = RequestNotSuccessful("Got 404 response")
        assert str(exc) == "Got 404 response"
        assert isinstance(exc, LaMarzoccoError)

    def test_bluetooth_connection_failed(self) -> None:
        """Test BluetoothConnectionFailed exception."""
        exc = BluetoothConnectionFailed("Could not connect")
        assert str(exc) == "Could not connect"
        assert isinstance(exc, LaMarzoccoError)

    def test_unknown_websocket_message(self) -> None:
        """Test UnknownWebSocketMessage exception."""
        exc = UnknownWebSocketMessage("Unknown message type")
        assert str(exc) == "Unknown message type"
        assert isinstance(exc, LaMarzoccoError)

    def test_cloud_only_functionality(self) -> None:
        """Test CloudOnlyFunctionality exception."""
        exc = CloudOnlyFunctionality()
        expected_msg = "Functionality is cloud only, but cloud client not initialized."
        assert str(exc) == expected_msg
        assert isinstance(exc, LaMarzoccoError)

    def test_unsupported_model(self) -> None:
        """Test UnsupportedModel exception."""
        exc = UnsupportedModel("Feature not available on this model")
        assert str(exc) == "Feature not available on this model"
        assert isinstance(exc, LaMarzoccoError)

    def test_exception_inheritance(self) -> None:
        """Test that all exceptions inherit properly."""
        exceptions = [
            AuthFail("test"),
            RequestNotSuccessful("test"),
            BluetoothConnectionFailed("test"),
            UnknownWebSocketMessage("test"),
            CloudOnlyFunctionality(),
            UnsupportedModel("test"),
        ]
        
        for exc in exceptions:
            assert isinstance(exc, LaMarzoccoError)
            assert isinstance(exc, Exception)

    def test_raising_exceptions(self) -> None:
        """Test that exceptions can be raised and caught."""
        with pytest.raises(AuthFail) as exc_info:
            raise AuthFail("Test auth failure")
        assert str(exc_info.value) == "Test auth failure"

        with pytest.raises(CloudOnlyFunctionality) as exc_info:
            raise CloudOnlyFunctionality()
        assert "cloud client not initialized" in str(exc_info.value)

        with pytest.raises(LaMarzoccoError):
            raise UnsupportedModel("Not supported")