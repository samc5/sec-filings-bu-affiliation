# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Python toolkit for downloading and analyzing SEC filings from the EDGAR database. The core module (`src/sec_filings/client.py`) provides a rate-limited client that handles SEC API requirements automatically.

## Setup and Development Commands

```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install in development mode
pip install -e .

# Run tests
pytest

# Run tests with coverage
pytest --cov=src/sec_filings --cov-report=html

# Format code
black src/ tests/ examples/

# Lint code
flake8 src/ tests/ examples/

# Type checking
mypy src/
```

## Architecture

### Core Module Structure

- `src/sec_filings/client.py`: Main `SECClient` class
  - Handles rate limiting (10 requests/second SEC limit)
  - Automatic User-Agent header management
  - Methods: `get_cik()`, `get_filings()`, `download_filing()`

- `src/sec_filings/exceptions.py`: Custom exceptions
  - `SECAPIError`, `RateLimitError`, `CompanyNotFoundError`, `FilingNotFoundError`

### Key Implementation Details

- **Rate Limiting**: Client enforces 0.1s minimum between requests using `_rate_limit()`
- **User Agent Requirement**: SEC requires contact info in User-Agent; validated at client initialization
- **CIK Format**: Central Index Keys are zero-padded 10-digit strings
- **Accession Numbers**: Format `0000320193-23-000077` used to identify specific filings

## Common SEC Filing Types

- **10-K**: Annual reports with comprehensive company information
- **10-Q**: Quarterly reports
- **8-K**: Current reports for major events
- **Form 4**: Insider trading reports
- **S-1**: IPO registration statements

## Example Usage Patterns

See `examples/fetch_company_filings.py` for basic fetching workflow:
1. Initialize client with User-Agent
2. Get CIK from ticker symbol
3. Fetch filings by type and date
4. Download specific filings

See `examples/parse_10k.py` for parsing 10-K sections using BeautifulSoup.
