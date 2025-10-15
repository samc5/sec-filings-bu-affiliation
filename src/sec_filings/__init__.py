"""SEC Filings - A toolkit for downloading and analyzing SEC filings."""

from .client import SECClient
from .exceptions import SECAPIError, RateLimitError
from .parser import FilingParser
from .affiliation_search import UniversityAffiliationFinder, AffiliationMatch
from .config import load_user_agent_from_env
from .cache import FilingCache
from .biography_extractor import BiographyExtractor, PersonAffiliation, is_spacy_available

__version__ = "0.1.0"
__all__ = [
    "SECClient",
    "SECAPIError",
    "RateLimitError",
    "FilingParser",
    "UniversityAffiliationFinder",
    "AffiliationMatch",
    "load_user_agent_from_env",
    "FilingCache",
    "BiographyExtractor",
    "PersonAffiliation",
    "is_spacy_available",
]
