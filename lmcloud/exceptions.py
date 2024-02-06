"""Exceptions for the lmcloud package."""


class AuthFail(Exception):
    """Error to indicate there is invalid auth info."""


class RequestNotSuccessful(Exception):
    """Error to indicate didn't get a 200 response"""


class BluetoothConnectionFailed(Exception):
    """Error to indicate we couldn't successfully connect through bluetooth"""


class UnknownWebSocketMessage(Exception):
    """Error to indicate we received an unknown websocket message"""


class ClientNotInitialized(Exception):
    """Error to indicate the client is not initialized"""
