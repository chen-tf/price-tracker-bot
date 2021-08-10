
class Error(Exception):
    """Base class for other exceptions"""
    pass


class ExceedLimitedSizeError(Error):
    """Raised when the user sub good size is over 11"""
    pass
