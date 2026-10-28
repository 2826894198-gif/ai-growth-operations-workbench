class AdsPowerError(Exception):
    """Base error for all AdsPower client failures."""


class AdsPowerUnavailable(AdsPowerError):
    """AdsPower Local API is unreachable or timed out."""


class AdsPowerAuthFailed(AdsPowerError):
    """AdsPower rejected the API key."""


class AdsPowerApiError(AdsPowerError):
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(f"AdsPower API error code={code} msg={message}")


class ProfileNotFound(AdsPowerError):
    pass


class ProfileStartFailed(AdsPowerError):
    pass


class ProfileStopFailed(AdsPowerError):
    pass
