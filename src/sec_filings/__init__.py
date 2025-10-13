"""SEC Filings - A toolkit for downloading and analyzing SEC filings."""

from .client import SECClient
from .exceptions import SECAPIError, RateLimitError
from .parser import FilingParser
from .affiliation_search import UniversityAffiliationFinder, AffiliationMatch
from .config import load_user_agent_from_env

__version__ = "0.1.0"
__all__ = [
    "SECClient",
    "SECAPIError",
    "RateLimitError",
    "FilingParser",
    "UniversityAffiliationFinder",
    "AffiliationMatch",
    "load_user_agent_from_env",
]
