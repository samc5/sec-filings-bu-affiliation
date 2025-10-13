# SEC Filings Research

A Python toolkit for downloading and analyzing SEC filings from the EDGAR database, with specialized tools for finding university affiliations in executive biographies.

## Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Quick Start

### Finding Boston University Affiliations

Search multiple companies for BU affiliations:
```bash
python examples/find_bu_affiliations.py
```

Search a specific company:
```bash
python examples/search_specific_filing.py AAPL DEF14A
```

Results are saved to `data/bu_affiliations.csv`.

### Basic API Usage

```python
from sec_filings import SECClient, UniversityAffiliationFinder

# Initialize client with your contact info (required by SEC)
client = SECClient(user_agent="Your Name your.email@example.com")

# Get company CIK (Central Index Key)
cik = client.get_cik("AAPL")

# Fetch recent proxy statements (best for biographical info)
filings = client.get_filings(cik, filing_type="DEF 14A", count=5)

# Download and search for BU affiliations
content = client.download_filing(filings[0]["accessionNumber"])
finder = UniversityAffiliationFinder()
matches = finder.search_filing(content)

for match in matches:
    print(f"{match.person_name}: {match.affiliation_type}")
```

## Examples

**University Affiliation Search:**
- `find_bu_affiliations.py`: Search multiple companies for BU affiliations
- `search_specific_filing.py`: Search a single company's latest filing

**Basic Filing Operations:**
- `fetch_company_filings.py`: Download filings for a specific company
- `parse_10k.py`: Extract sections from 10-K filings

## Features

- **Rate-limited SEC EDGAR API client** - Automatically respects SEC's 10 requests/second limit
- **Biography extraction** - Finds biographical sections in proxy statements and 10-Ks
- **University affiliation detection** - Identifies degrees, positions, and other affiliations
- **Confidence scoring** - Classifies matches as high/medium/low confidence
- **CSV export** - Save search results for further analysis

## Project Structure

- `src/sec_filings/`: Main package code
- `tests/`: Unit tests
- `examples/`: Example scripts
- `data/`: Downloaded filings (gitignored)
- `docs/`: Additional documentation
