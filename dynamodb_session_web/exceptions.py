class SessionError(Exception):
    loggable_sid: str

    def __init__(self, loggable_sid: str = ''):
        self.loggable_sid = loggable_sid
        super().__init__()


class SessionNotFoundError(SessionError):
    """Raised when a session ID is not found in the database. This differs from InvalidSessionIdError, in that
    the session ID appears to be valid, or is not using HMAC for generation.
    """
    def __str__(self) -> str:
        return f'SessionNotFoundError: {self.loggable_sid}'


class InvalidSessionIdError(SessionError):
    """Raised when using HMAC for session ID generation, and the ID is not valid."""
    def __str__(self) -> str:
        return f'InvalidSessionIdError: {self.loggable_sid}'
