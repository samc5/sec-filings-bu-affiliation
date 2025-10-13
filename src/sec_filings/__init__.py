"""SEC Filings - A toolkit for downloading and analyzing SEC filings."""

from .client import SECClient
from .exceptions import SECAPIError, RateLimitError
from .parser import FilingParser
from .affiliation_search import UniversityAffiliationFinder, AffiliationMatch

__version__ = "0.1.0"
__all__ = [
    "SECClient",
    "SECAPIError",
    "RateLimitError",
    "FilingParser",
    "UniversityAffiliationFinder",
    "AffiliationMatch",
]
