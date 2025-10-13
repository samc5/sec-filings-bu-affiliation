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

**Search multiple companies** (`examples/find_bu_affiliations.py`):
```bash
python examples/find_bu_affiliations.py
```
- Searches proxy statements (DEF 14A) and 10-Ks for BU affiliations
- Outputs CSV file with all matches to `data/bu_affiliations.csv`
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
