class Error(Exception):
    """Base class for other exceptions"""
    pass


class ExceedLimitedSizeError(Error):
    """Raised when the user sub good size is over 11"""
    pass


class CrawlerParseError(Error):
    """Raised when parse momo good's info page error."""
    pass


class NotValidMomoURL(Error):
    """Raised when url not valid."""
    pass


class UnknownRequestError(Error):
    """Raised when request unknown error"""
    pass


class GoodNotExist(Error):
    """Raised when good not exist."""
    pass
