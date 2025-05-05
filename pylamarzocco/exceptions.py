"""Exceptions for the pylamarzocco package."""


class LaMarzoccoError(Exception):
    """Base exception for the La Marzocco package."""


class AuthFail(LaMarzoccoError):
    """Error to indicate there is invalid auth info."""


class RequestNotSuccessful(LaMarzoccoError):
    """Error to indicate didn't get a 200 response"""


class BluetoothConnectionFailed(LaMarzoccoError):
    """Error to indicate we couldn't successfully connect through bluetooth"""


class UnknownWebSocketMessage(LaMarzoccoError):
    """Error to indicate we received an unknown websocket message"""


class CloudOnlyFunctionality(LaMarzoccoError):
    """Error to indicate the client is not initialized"""

    def __init__(self) -> None:
        """Initialize the exception."""
        super().__init__(
            "Functionality is cloud only, but cloud client not initialized."
        )


class UnsupportedModel(LaMarzoccoError):
    """Raised when a certain functionality is only available on certain models."""
