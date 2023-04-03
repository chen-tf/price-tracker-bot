class Error(Exception):
    """Base class for other exceptions"""

    pass


class ExceedLimitedSizeException(Error):
    """Raised when the user sub good size is over 11"""

    pass


class CrawlerParseException(Error):
    """Raised when parse momo good's info page error."""

    pass


class NotValidMomoURLException(Error):
    """Raised when url not valid."""

    pass


class UnknownRequestException(Error):
    """Raised when request unknown error"""

    pass


class GoodNotException(Error):
    """Raised when good not exist."""

    pass


class EmptyPageException(Error):
    """Raised when page is empty."""

    pass
