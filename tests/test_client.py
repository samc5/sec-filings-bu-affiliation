"""Tests for SEC client."""

import pytest
from src.sec_filings import SECClient
from src.sec_filings.exceptions import SECAPIError


def test_client_requires_valid_user_agent():
    """Test that client requires a valid user agent with email."""
    with pytest.raises(ValueError):
        SECClient(user_agent="")

    with pytest.raises(ValueError):
        SECClient(user_agent="No Email Here")

    # Should succeed with email
    client = SECClient(user_agent="Test test@example.com")
    assert client.user_agent == "Test test@example.com"


def test_rate_limiting():
    """Test that rate limiting is enforced."""
    import time

    client = SECClient(user_agent="Test test@example.com")

    # Should enforce minimum interval between requests
    start = time.time()
    client._rate_limit()
    client._rate_limit()
    elapsed = time.time() - start

    # Should take at least the minimum interval
    assert elapsed >= client._min_request_interval


# Note: The following tests would require either mocking or actual API calls
# For real testing, you would want to:
# 1. Mock the requests using pytest-mock or responses library
# 2. Create integration tests that run separately with real API calls
# 3. Use VCR.py to record and replay HTTP interactions


def test_get_cik_format():
    """Test CIK format (zero-padded 10 digits)."""
    # This would need mocking in a real test
    # client = SECClient(user_agent="Test test@example.com")
    # cik = client.get_cik("AAPL")
    # assert len(cik) == 10
    # assert cik.isdigit()
    pass


def test_get_filings_returns_list():
    """Test that get_filings returns a list of filings."""
    # This would need mocking in a real test
    # client = SECClient(user_agent="Test test@example.com")
    # filings = client.get_filings("0000320193", filing_type="10-K", count=5)
    # assert isinstance(filings, list)
    # if filings:
    #     assert "type" in filings[0]
    #     assert "date" in filings[0]
    #     assert "accessionNumber" in filings[0]
    pass
