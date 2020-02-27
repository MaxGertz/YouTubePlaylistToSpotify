class ResponseException(Exception):
    def __init__(self, code, message=""):
        self.message = message
        self.code = code

    def __str__(self):
        return self.message + f"Response gave status code {self.code}"
