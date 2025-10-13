## Copilot / AI Agent Quick Guide for sec-filings

This repo is a small Python toolkit for downloading and parsing SEC EDGAR filings.
Keep instructions concise and preserve existing behavior (esp. User-Agent validation and rate limiting).

- Where to look
  - Core package: `src/sec_filings/` — primary files: `client.py` (SECClient) and `exceptions.py`.
  - Examples: `examples/fetch_company_filings.py` and `examples/parse_10k.py` show intended usage.
  - Tests: `tests/test_client.py` contains unit checks (no network in CI-style tests).
  - Docs & notes: `README.md` and `CLAUDE.md` (useful background and commands).

- Big picture architecture (short)
  - SECClient in `client.py` wraps the EDGAR browse/search endpoints. It centralizes HTTP access via a
    `requests.Session`, enforces a minimum request interval (`_min_request_interval = 0.1`) and validates
    the required User-Agent header that must include contact info (an email).
  - Parsing is done with BeautifulSoup (`lxml` parser) against EDGAR HTML pages. Filings are located by
    scraping the `table` with class `tableFile2` and locating the documents link with `id="documentsbutton"`.

- Project-specific constraints and patterns
  - User-Agent required: the constructor raises ValueError if the `user_agent` string doesn't contain an `@`.
    Example: `SECClient(user_agent="Your Name your.email@example.com")`.
  - Rate limiting: client enforces a 0.1s minimum between requests via `_rate_limit()`; preserve this behavior.
  - CIK format: CIKs are stored/returned as zero-padded 10-digit strings (e.g., `0000320193`). Use `.zfill(10)`.
  - Accession numbers: used as identifiers like `0000320193-23-000077`. `download_filing()` expects this form.

- HTTP & parsing details to preserve
  - Base URL constants: `BASE_URL = "https://www.sec.gov"` and `COMPANY_SEARCH_URL`/`EDGAR_SEARCH_URL` usage.
  - Use `requests.Session()` and set headers on the session (do not bypass Session headers).
  - Parsing assumptions: `get_filings()` expects a `table.tableFile2` structure and extracts columns by index.
    If modifying parsing logic, add tests using recorded/synthetic HTML samples.

- Developer workflows / commands (discoverable from repo)
  - Setup virtualenv and install deps: `python -m venv venv && source venv/bin/activate && pip install -r requirements.txt`.
  - Install in editable/dev mode: `pip install -e .` (useful when running examples locally).
  - Run tests: `pytest` (tests live in `tests/`, pytest configured in pyproject.toml).
  - Formatting & linting: `black src/ tests/ examples/`, `flake8 src/ tests/ examples/`, `mypy src/`.

- Tests and network policy
  - Unit tests are written to avoid real network calls; integration tests should be mocked (use `responses`, `requests-mock`,
    or VCR.py) if you add network-dependent tests. The existing `tests/test_client.py` includes format and rate-limit checks.

- Examples (how to run)
  - Examples prepend `src/` onto `sys.path` for local development. To run: `python examples/fetch_company_filings.py` but
    replace the example `user_agent` string with a real contact email.
  - Output files are written to `data/` (project-local download folder); this directory is used by examples and is gitignored.

- When editing the client surface
  - Preserve public API shape: `SECClient(user_agent)`, methods: `get_cik(ticker)`, `get_filings(cik, filing_type, count, before_date)`,
    `download_filing(accession_number, save_path=None)`.
  - Keep exception types in `exceptions.py` (`SECAPIError`, `RateLimitError`, `CompanyNotFoundError`, `FilingNotFoundError`).
  - Add unit tests that mock `requests.Session.get` or use a HTTP-recording tool for any changes that touch parsing or endpoints.

- Quick hints for Copilot/AI edits
  - Use small, well-tested commits. Add a test for every behavior change (parsing tweaks, header changes, rate-limit tuning).
  - Prefer non-invasive improvements: add optional arguments (e.g., `session: Optional[requests.Session] = None`) rather than
    changing constructor semantics.
  - Document any edge-case behavior in `README.md` and update examples.

If any of this guide is unclear or you want more detail in a specific area (tests, parsing heuristics, or adding integration tests),
tell me which part to expand and I will iterate.
