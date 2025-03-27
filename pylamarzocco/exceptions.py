"""Exceptions for the pylamarzocco package."""


class AuthFail(Exception):
    """Error to indicate there is invalid auth info."""


class RequestNotSuccessful(Exception):
    """Error to indicate didn't get a 200 response"""


class BluetoothConnectionFailed(Exception):
    """Error to indicate we couldn't successfully connect through bluetooth"""


class UnknownWebSocketMessage(Exception):
    """Error to indicate we received an unknown websocket message"""


class CloudOnlyFunctionality(Exception):
    """Error to indicate the client is not initialized"""

    def __init__(self) -> None:
        """Initialize the exception."""
        super().__init__(
            "Functionality is cloud only, but cloud client not initialized."
        )


class UnsupportedModel(Exception):
    """Raised when a certain functionality is only available on certain models."""
