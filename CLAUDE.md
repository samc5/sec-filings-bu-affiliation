# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Python toolkit for downloading and analyzing SEC filings from the EDGAR database, with specialized functionality for finding university affiliations in executive biographies. Primary use case: identifying people with Boston University affiliations mentioned in SEC filings.

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
  - New: `get_company_tickers_list()`: Fetch all ~13,000 companies from SEC index
  - New: `get_recent_filings_bulk()`: Search filings across all companies by date range

- `src/sec_filings/parser.py`: Filing content parser
  - `FilingParser.extract_text_from_html()`: Clean HTML to text
  - `FilingParser.find_biographical_sections()`: Extract bio sections from filings (Item 10, Director bios, etc.)
  - `FilingParser.extract_individual_bios()`: Parse individual person biographies with name/age/bio

- `src/sec_filings/affiliation_search.py`: University affiliation finder
  - `UniversityAffiliationFinder`: Search for university mentions in bios
  - Default patterns for Boston University (BU, Boston University, Boston U.)
  - Classifies affiliations by type: degree, position, education, employment, or general mention
  - Returns `AffiliationMatch` objects with person name, type, context, and confidence level

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

### Basic Filing Retrieval
See `examples/fetch_company_filings.py` for basic fetching workflow:
1. Initialize client with User-Agent
2. Get CIK from ticker symbol
3. Fetch filings by type and date
4. Download specific filings

### Finding University Affiliations

**RECOMMENDED: Search by year range** (`examples/search_by_year_range.py`):
```bash
# Search all companies that filed between 2020-2024
python examples/search_by_year_range.py --start-year 2020 --end-year 2024

# Test mode (only first 50 companies)
python examples/search_by_year_range.py --start-year 2023 --end-year 2024 --test-mode

# Customize filing types and max filings per company
python examples/search_by_year_range.py --start-year 2023 --end-year 2024 --filing-types "DEF 14A,10-K" --max-per-company 2
```
- Fetches complete SEC company index (~13,000 companies)
- Gets recent filings for each company in date range
- Searches biographical sections for BU mentions
- Saves results to `data/bu_affiliations_YYYY-MM-DD.csv`
- Uses progress tracking and periodic saves
- Can take 30+ minutes for comprehensive searches

**Search specific companies** (`examples/find_bu_affiliations.py`):
```bash
python examples/find_bu_affiliations.py
```
- Searches proxy statements (DEF 14A) and 10-Ks for BU affiliations
- Edit the `tickers` list in the script to customize which companies to search

**Search single company** (`examples/search_specific_filing.py`):
```bash
python examples/search_specific_filing.py AAPL DEF14A
python examples/search_specific_filing.py MSFT 10-K
```

### Best Filing Types for Biographical Information

1. **DEF 14A (Proxy Statement)**: Best source - contains detailed director/executive bios
2. **10-K (Annual Report)**: Item 10 contains director and executive officer information
3. **S-1 (IPO Registration)**: Management section has comprehensive bios

The affiliation finder automatically searches these biographical sections.
