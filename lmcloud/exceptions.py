class AuthFail(Exception):
    """Error to indicate there is invalid auth info."""

    def __init__(self, msg):
        super().__init__(msg)


class RequestNotSuccessful(Exception):
    """Error to indicate didn't get a 200 response"""

    def __init__(self, msg):
        super().__init__(msg)

class BluetoothDeviceNotFound(Exception):
    """Error to indicate we couldn't successfully connect through bluetooth"""
    
    def __init__(self, msg):
        super().__init__(msg)
