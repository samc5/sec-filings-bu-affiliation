"""SEC EDGAR API client for fetching company filings."""

import time
from typing import List, Dict, Optional, Any
import requests
from bs4 import BeautifulSoup

from .exceptions import SECAPIError, RateLimitError, CompanyNotFoundError, FilingNotFoundError


class SECClient:
    """Client for interacting with the SEC EDGAR database.

    The SEC requires all automated requests to include a User-Agent header
    with contact information. Rate limit is 10 requests per second.
    """

    BASE_URL = "https://www.sec.gov"
    EDGAR_SEARCH_URL = f"{BASE_URL}/cgi-bin/browse-edgar"
    COMPANY_SEARCH_URL = f"{BASE_URL}/cgi-bin/browse-edgar"

    def __init__(self, user_agent: str):
        """Initialize SEC client.

        Args:
            user_agent: User agent string with contact info (e.g., "Name email@example.com")
        """
        if not user_agent or "@" not in user_agent:
            raise ValueError(
                "user_agent must include contact information (e.g., 'Your Name email@example.com')"
            )

        self.user_agent = user_agent
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent})
        self._last_request_time = 0.0
        self._min_request_interval = 0.1  # 10 requests per second max

    def _rate_limit(self) -> None:
        """Enforce rate limiting to respect SEC's 10 requests/second limit."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_request_interval:
            time.sleep(self._min_request_interval - elapsed)
        self._last_request_time = time.time()

    def _make_request(self, url: str, params: Optional[Dict[str, Any]] = None) -> requests.Response:
        """Make a rate-limited request to SEC EDGAR.

        Args:
            url: URL to request
            params: Query parameters

        Returns:
            Response object

        Raises:
            RateLimitError: If rate limit is exceeded
            SECAPIError: For other API errors
        """
        self._rate_limit()

        try:
            response = self.session.get(url, params=params, timeout=30)

            if response.status_code == 429:
                raise RateLimitError("SEC rate limit exceeded. Please slow down requests.")

            response.raise_for_status()
            return response

        except requests.exceptions.RequestException as e:
            raise SECAPIError(f"Request failed: {str(e)}")

    def get_cik(self, ticker: str) -> str:
        """Get CIK (Central Index Key) for a company ticker symbol.

        Args:
            ticker: Stock ticker symbol (e.g., "AAPL")

        Returns:
            CIK as a zero-padded 10-digit string

        Raises:
            CompanyNotFoundError: If ticker is not found
        """
        params = {
            "action": "getcompany",
            "company": ticker,
            "type": "",
            "dateb": "",
            "owner": "exclude",
            "count": "1",
        }

        response = self._make_request(self.COMPANY_SEARCH_URL, params=params)
        soup = BeautifulSoup(response.text, "lxml")

        # Look for CIK in the company info section
        cik_element = soup.find("span", class_="companyName")
        if not cik_element:
            raise CompanyNotFoundError(f"Company with ticker '{ticker}' not found")

        # Extract CIK from text like "APPLE INC (0000320193)"
        cik_text = cik_element.get_text()
        if "(" in cik_text and ")" in cik_text:
            cik = cik_text.split("(")[-1].split(")")[0].strip()
            return cik.zfill(10)

        raise CompanyNotFoundError(f"Could not extract CIK for ticker '{ticker}'")

    def get_filings(
        self,
        cik: str,
        filing_type: str = "",
        count: int = 100,
        before_date: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        """Get list of filings for a company.

        Args:
            cik: Company CIK (Central Index Key)
            filing_type: Type of filing (e.g., "10-K", "10-Q", "8-K"). Empty string for all.
            count: Number of filings to return (max 100)
            before_date: Only return filings before this date (YYYYMMDD format)

        Returns:
            List of filing dictionaries with keys: type, date, accessionNumber, url
        """
        params = {
            "action": "getcompany",
            "CIK": cik,
            "type": filing_type,
            "dateb": before_date or "",
            "owner": "exclude",
            "count": min(count, 100),
            "search_text": "",
        }

        response = self._make_request(self.COMPANY_SEARCH_URL, params=params)
        soup = BeautifulSoup(response.text, "lxml")

        filings = []
        filing_table = soup.find("table", class_="tableFile2")

        if not filing_table:
            return filings

        rows = filing_table.find_all("tr")[1:]  # Skip header row

        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 4:
                continue

            filing_type_col = cols[0].get_text(strip=True)
            date_col = cols[3].get_text(strip=True)

            # Find the documents link
            doc_link = cols[1].find("a", {"id": "documentsbutton"})
            if not doc_link:
                continue

            doc_url = doc_link.get("href", "")
            if not doc_url:
                continue

            # Extract accession number from URL
            # URL format: /cgi-bin/viewer?action=view&cik=...&accession_number=...
            accession_number = doc_url.split("accession_number=")[-1].split("&")[0] if "accession_number=" in doc_url else ""

            filings.append({
                "type": filing_type_col,
                "date": date_col,
                "accessionNumber": accession_number,
                "url": f"{self.BASE_URL}{doc_url}" if doc_url.startswith("/") else doc_url,
            })

        return filings

    def download_filing(self, accession_number: str, save_path: Optional[str] = None) -> str:
        """Download a filing document.

        Args:
            accession_number: Filing accession number (e.g., "0000320193-23-000077")
            save_path: Optional path to save the filing. If None, returns content as string.

        Returns:
            Filing content as string (or path if saved)

        Raises:
            FilingNotFoundError: If filing is not found
        """
        # Remove dashes from accession number for URL
        acc_no_dashes = accession_number.replace("-", "")

        # Construct the filing URL
        url = f"{self.BASE_URL}/cgi-bin/viewer?action=view&cik=0&accession_number={accession_number}"

        response = self._make_request(url)

        if response.status_code == 404:
            raise FilingNotFoundError(f"Filing {accession_number} not found")

        content = response.text

        if save_path:
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(content)
            return save_path

        return content
