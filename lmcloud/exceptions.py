"""Exceptions for the lmcloud package."""


class AuthFail(Exception):
    """Error to indicate there is invalid auth info."""


class RequestNotSuccessful(Exception):
    """Error to indicate didn't get a 200 response"""


class BluetoothDeviceNotFound(Exception):
    """Error to indicate we couldn't find the machine through bluetooth"""


class BluetoothConnectionFailed(Exception):
    """Error to indicate we couldn't successfully connect through bluetooth"""


class UnknownWebSocketMessage(Exception):
    """Error to indicate we received an unknown websocket message"""


class MachineNotFound(Exception):
    """Error to indicate we couldn't find the machine through the API"""
