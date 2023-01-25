class AuthFail(Exception):
    """Error to indicate there is invalid auth info."""

    def __init__(self, msg):
        super().__init__(msg)