"""Custom exceptions for SEC filings API."""


class SECAPIError(Exception):
    """Base exception for SEC API errors."""
    pass


class RateLimitError(SECAPIError):
    """Raised when SEC rate limit is exceeded."""
    pass


class CompanyNotFoundError(SECAPIError):
    """Raised when a company cannot be found."""
    pass


class FilingNotFoundError(SECAPIError):
    """Raised when a filing cannot be found."""
    pass
