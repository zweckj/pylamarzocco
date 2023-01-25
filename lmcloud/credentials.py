class Credentials:

    def __init__(self, client_id, client_secret, username, password):
        self.client_id = client_id
        self.client_secret = client_secret
        self.username = username
        self.password = password

    @property
    def client_id(self):
        return self.client_id

    @property
    def client_secret(self):
        return self.client_secret

    @property
    def username(self):
        return self.username

    @property
    def password(self):
        return self.password