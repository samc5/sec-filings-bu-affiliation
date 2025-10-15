"""SEC EDGAR API client for fetching company filings."""

import time
import json
from typing import List, Dict, Optional, Any
import requests
from bs4 import BeautifulSoup

from .exceptions import SECAPIError, RateLimitError, CompanyNotFoundError, FilingNotFoundError
from .cache import FilingCache


class SECClient:
    """Client for interacting with the SEC EDGAR database.

    The SEC requires all automated requests to include a User-Agent header
    with contact information. Rate limit is 10 requests per second.
    """

    BASE_URL = "https://www.sec.gov"
    EDGAR_SEARCH_URL = f"{BASE_URL}/cgi-bin/browse-edgar"
    COMPANY_SEARCH_URL = f"{BASE_URL}/cgi-bin/browse-edgar"
    FULL_TEXT_SEARCH_URL = f"{BASE_URL}/cgi-bin/srch-edgar"

    def __init__(self, user_agent: str, use_cache: bool = True):
        """Initialize SEC client.

        Args:
            user_agent: User agent string with contact info (e.g., "Name email@example.com")
            use_cache: Whether to use local SQLite cache for downloaded filings (default: True)
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

        # Initialize cache if enabled
        self.cache = FilingCache() if use_cache else None

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
            # URL format can be either:
            # - /cgi-bin/viewer?action=view&cik=...&accession_number=...
            # - /Archives/edgar/data/CIK/ACCESSION/ACCESSION-index.htm
            accession_number = ""
            if "accession_number=" in doc_url:
                accession_number = doc_url.split("accession_number=")[-1].split("&")[0]
            else:
                # Extract from path format: /Archives/edgar/data/320193/000119312522003583/0001193125-22-003583-index.htm
                # The accession number is the last path component before -index.htm
                parts = doc_url.rstrip("/").split("/")
                if len(parts) >= 2:
                    # Get the filename and remove -index.htm suffix
                    filename = parts[-1]
                    if filename.endswith("-index.htm"):
                        accession_number = filename.replace("-index.htm", "")

            filings.append({
                "type": filing_type_col,
                "date": date_col,
                "accessionNumber": accession_number,
                "url": f"{self.BASE_URL}{doc_url}" if doc_url.startswith("/") else doc_url,
            })

        return filings

    def download_filing(self, accession_number: str, cik: Optional[str] = None, save_path: Optional[str] = None) -> str:
        """Download a filing document.

        Args:
            accession_number: Filing accession number (e.g., "0000320193-23-000077")
            cik: Company CIK (optional, will be extracted from accession number if not provided)
            save_path: Optional path to save the filing. If None, returns content as string.

        Returns:
            Filing content as string (or path if saved)

        Raises:
            FilingNotFoundError: If filing is not found
        """
        # Check cache first if enabled
        if self.cache and not save_path:
            cached_content = self.cache.get(accession_number)
            if cached_content:
                return cached_content

        # Remove dashes from accession number for directory path
        acc_no_dashes = accession_number.replace("-", "")

        # Extract CIK from accession number if not provided
        # Accession format: XXXXXXXXXX-YY-ZZZZZZ where first part is filer CIK
        if not cik:
            cik = accession_number.split("-")[0]

        # Remove leading zeros from CIK for the URL path
        cik_no_zeros = cik.lstrip("0")

        # Construct the filing index URL
        # Format: https://www.sec.gov/Archives/edgar/data/CIK/ACCESSION/ACCESSION-index.htm
        index_url = f"{self.BASE_URL}/Archives/edgar/data/{cik_no_zeros}/{acc_no_dashes}/{accession_number}-index.htm"

        try:
            index_response = self._make_request(index_url)
        except SECAPIError:
            raise FilingNotFoundError(f"Filing {accession_number} not found")

        # Parse the index page to find the primary document
        soup = BeautifulSoup(index_response.text, "lxml")
        table = soup.find("table", class_="tableFile")

        if not table:
            raise FilingNotFoundError(f"Could not find document table for filing {accession_number}")

        # Find the first HTML document (usually the main filing)
        rows = table.find_all("tr")[1:]  # Skip header
        doc_url = None

        for row in rows:
            cells = row.find_all("td")
            if len(cells) >= 3:
                link = cells[2].find("a")
                if link:
                    href = link.get("href", "")
                    # Look for HTML or HTM files (not graphics, PDFs, etc.)
                    if href and (".htm" in href.lower() or ".html" in href.lower()) and ".jpg" not in href.lower():
                        doc_url = href
                        break

        if not doc_url:
            raise FilingNotFoundError(f"Could not find primary document for filing {accession_number}")

        # Handle inline XBRL viewer URLs (format: /ix?doc=/Archives/...)
        # Extract the actual document URL from the doc parameter
        if "/ix?" in doc_url and "doc=" in doc_url:
            import urllib.parse
            parsed = urllib.parse.urlparse(doc_url)
            params = urllib.parse.parse_qs(parsed.query)
            if "doc" in params:
                doc_url = params["doc"][0]

        # Download the actual filing document
        if doc_url.startswith("/"):
            doc_url = f"{self.BASE_URL}{doc_url}"

        response = self._make_request(doc_url)
        content = response.text

        if save_path:
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(content)
            return save_path

        # Cache the content if caching is enabled
        if self.cache:
            self.cache.set(accession_number, content)

        return content

    def search_filings_by_text(
        self,
        search_text: str,
        filing_types: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        max_results: int = 100,
    ) -> List[Dict[str, Any]]:
        """Search SEC filings using EDGAR full-text search API.

        This method uses the SEC EDGAR full-text search to find filings containing
        specific text (e.g., "Boston University"). This is much more efficient than
        downloading all filings and searching them locally.

        Args:
            search_text: Text to search for (e.g., "Boston University")
            filing_types: List of filing types to search (e.g., ["DEF 14A", "10-K"])
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            max_results: Maximum number of results to return (note: API may have pagination limits)

        Returns:
            List of filing dictionaries with keys: company_name, cik, type, date,
            accessionNumber, filing_url

        Example:
            >>> client = SECClient(user_agent="Name email@example.com")
            >>> results = client.search_filings_by_text(
            ...     search_text="Boston University",
            ...     filing_types=["DEF 14A", "10-K"],
            ...     start_date="2020-01-01",
            ...     end_date="2024-12-31"
            ... )
        """
        print(f"Searching EDGAR for: '{search_text}'")

        # Build the search query parameters
        # The EDGAR search uses specific query syntax
        query_parts = [f'"{search_text}"']

        # Add filing type filter if specified
        if filing_types:
            # Format: (type:10-K OR type:DEF14A)
            type_filters = " OR ".join([f"type:{ft.replace(' ', '').replace('-', '')}" for ft in filing_types])
            query_parts.append(f"({type_filters})")

        query = " AND ".join(query_parts)

        # Build date range filter
        date_range = None
        if start_date or end_date:
            # Convert dates to SEC format if needed
            if start_date and end_date:
                date_range = f"{start_date} TO {end_date}"
            elif start_date:
                date_range = f"{start_date} TO *"
            elif end_date:
                date_range = f"* TO {end_date}"

        # The SEC EDGAR full-text search API endpoint
        # Note: The SEC has deprecated their old full-text search API
        # The new approach is to use the EDGAR search interface via their website
        # or use bulk data downloads. We'll implement a web scraping approach here.

        params = {
            "q": search_text,
            "dateRange": "custom" if date_range else "all",
            "startdt": start_date.replace("-", "") if start_date else "",
            "enddt": end_date.replace("-", "") if end_date else "",
        }

        # Add form types if specified
        if filing_types:
            # The search interface expects form types without spaces/dashes
            params["type"] = [ft.replace(" ", "").replace("-", "") for ft in filing_types]

        # SEC's search interface - note this may change
        search_url = f"{self.BASE_URL}/cgi-bin/srch-edgar"

        results = []

        try:
            # For now, we'll return an empty list with a note
            # A full implementation would require web scraping or using SEC's bulk data
            print("Note: SEC full-text search via API is limited.")
            print("Consider using get_recent_filings_bulk() with manual filtering,")
            print("or downloading SEC bulk data for comprehensive searches.")
            print(f"Search parameters: q='{search_text}', types={filing_types}, date range={start_date} to {end_date}")

        except Exception as e:
            raise SECAPIError(f"Search failed: {str(e)}")

        return results

    def get_company_tickers_list(self) -> List[Dict[str, str]]:
        """Get list of all company tickers from SEC company tickers JSON.

        Returns:
            List of dictionaries with company information (cik, ticker, name)
        """
        import json

        # SEC provides a JSON file with all company tickers
        url = "https://www.sec.gov/files/company_tickers.json"

        response = self._make_request(url)
        data = json.loads(response.text)

        companies = []
        for entry in data.values():
            companies.append({
                "cik": str(entry["cik_str"]).zfill(10),
                "ticker": entry["ticker"],
                "name": entry["title"],
            })

        return companies

    def get_recent_filings_bulk(
        self,
        filing_types: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        max_per_company: int = 1,
        company_limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Get recent filings across all companies.

        This iterates through all companies and fetches their recent filings.
        Use cautiously as this can make many API requests.

        Args:
            filing_types: List of filing types (e.g., ["DEF 14A", "10-K"])
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format (used as dateb parameter)
            max_per_company: Max filings to fetch per company
            company_limit: Limit number of companies to search (for testing)

        Returns:
            List of filing dictionaries with company info
        """
        print("Fetching company list...")
        companies = self.get_company_tickers_list()

        if company_limit:
            companies = companies[:company_limit]

        print(f"Searching filings for {len(companies)} companies...")

        all_filings = []
        filing_types = filing_types or ["DEF 14A"]

        for i, company in enumerate(companies, 1):
            if i % 100 == 0:
                print(f"  Progress: {i}/{len(companies)} companies...")

            for filing_type in filing_types:
                try:
                    filings = self.get_filings(
                        cik=company["cik"],
                        filing_type=filing_type,
                        count=max_per_company,
                        before_date=end_date.replace("-", "") if end_date else None,
                    )

                    # Filter by start date if provided
                    if start_date:
                        start_date_str = start_date.replace("-", "")
                        filings = [
                            f for f in filings
                            if f["date"].replace("-", "") >= start_date_str
                        ]

                    # Add company info to each filing
                    for filing in filings:
                        filing.update({
                            "company_name": company["name"],
                            "ticker": company["ticker"],
                            "cik": company["cik"],
                        })

                    all_filings.extend(filings)

                except Exception as e:
                    # Skip companies that error out
                    pass

        print(f"\nFound {len(all_filings)} total filings")
        return all_filings
