"""SEC Filings - A toolkit for downloading and analyzing SEC filings."""

from .client import SECClient
from .exceptions import SECAPIError, RateLimitError

__version__ = "0.1.0"
__all__ = ["SECClient", "SECAPIError", "RateLimitError"]
