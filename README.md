# SEC Filings Research

A Python toolkit for downloading and analyzing SEC filings from the EDGAR database, with specialized tools for finding university affiliations in executive biographies.

## Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install SpaCy language model for NLP features
python -m spacy download en_core_web_sm

# Configure SEC API access (REQUIRED)
# Copy the example .env file and add your contact information
cp .env.example .env
# Edit .env and set:
#   SEC_USER_NAME=Your Name
#   SEC_USER_EMAIL=your.email@example.com
```

**Important:** The SEC requires that all API requests include contact information in the User-Agent header. The scripts will not run without a properly configured `.env` file with your name and email.

### NLP-Based Extraction (New in v0.1.0)

This toolkit now includes NLP-based person name extraction using [SpaCy](https://spacy.io/), which provides:
- **More accurate name extraction** using Named Entity Recognition (NER) instead of regex patterns
- **Better context understanding** using dependency parsing
- **Intelligent affiliation detection** for degrees, positions, and employment

The NLP features are optional but recommended for better results. If SpaCy is not installed, the toolkit will fall back to pattern-based extraction.

**Benefits of NLP-based extraction:**
- Eliminates name extraction errors (e.g., incorrect person names)
- Better understanding of relationships between people and organizations
- More accurate degree and position extraction
- Improved confidence scoring

## Quick Start

### Finding Boston University Affiliations

**Recommended: Search by year range** (searches all companies):
```bash
# Search all filings from 2020-2024
python examples/search_by_year_range.py --start-year 2020 --end-year 2024

# Test mode (searches only first 50 companies)
python examples/search_by_year_range.py --start-year 2023 --end-year 2024 --test-mode

# Customize filing types
python examples/search_by_year_range.py --start-year 2023 --end-year 2024 --filing-types "DEF 14A,10-K,S-1"
```

**Search specific companies:**
```bash
# Search multiple predefined companies
python examples/find_bu_affiliations.py

# Search a single company's latest filing
python examples/search_specific_filing.py AAPL DEF14A
```

Results are saved to `data/bu_affiliations_YYYY-MM-DD.csv`.

### Basic API Usage

**Pattern-based extraction (original):**
```python
from sec_filings import SECClient, UniversityAffiliationFinder, load_user_agent_from_env

# Initialize client with caching enabled (loads contact info from .env file)
client = SECClient(user_agent=load_user_agent_from_env(), use_cache=True)

# Get company CIK (Central Index Key)
cik = client.get_cik("AAPL")

# Fetch recent proxy statements (best for biographical info)
filings = client.get_filings(cik, filing_type="DEF 14A", count=5)

# Download and search for BU affiliations (uses cache if available)
content = client.download_filing(filings[0]["accessionNumber"])
finder = UniversityAffiliationFinder()
matches = finder.search_filing(content)

for match in matches:
    print(f"{match.person_name}: {match.affiliation_type}")
```

**NLP-based extraction (recommended):**
```python
from sec_filings import (
    SECClient, BiographyExtractor, FilingParser,
    load_user_agent_from_env, is_spacy_available
)

# Check if SpaCy is available
if not is_spacy_available():
    print("SpaCy not available. Install with: pip install spacy")
    print("Then: python -m spacy download en_core_web_sm")
    exit(1)

# Initialize client and extractor
client = SECClient(user_agent=load_user_agent_from_env(), use_cache=True)
extractor = BiographyExtractor()
parser = FilingParser()

# Download filing
cik = client.get_cik("AAPL")
filings = client.get_filings(cik, filing_type="DEF 14A", count=1)
content = client.download_filing(filings[0]["accessionNumber"])

# Extract biographical sections
bio_sections = parser.find_biographical_sections(content)

# Search for affiliations using NLP
for section in bio_sections:
    text = section["content"]
    affiliations = extractor.extract_affiliations(
        text,
        organization_names=["Boston University", "BU", "Boston U."]
    )

    for aff in affiliations:
        print(f"{aff.person_name}: {aff.affiliation_type}")
        if aff.degree:
            print(f"  Degree: {aff.degree}" + (f" ({aff.degree_year})" if aff.degree_year else ""))
        if aff.position:
            print(f"  Position: {aff.position}")
```

## Examples

**University Affiliation Search:**
- `search_by_year_range.py`: **[RECOMMENDED]** Search all SEC filings by year range for BU affiliations
- `find_bu_affiliations.py`: Search specific list of companies for BU affiliations
- `search_specific_filing.py`: Search a single company's latest filing

**Basic Filing Operations:**
- `fetch_company_filings.py`: Download filings for a specific company
- `parse_10k.py`: Extract sections from 10-K filings

## Search Approaches

### Year Range Search (Recommended)
The `search_by_year_range.py` script searches **all companies** that filed during a time period:
- Fetches the complete SEC company index (~13,000 companies)
- Gets recent filings for each company in the date range
- Searches each filing for Boston University mentions
- Can take 30+ minutes for comprehensive searches
- Best for finding all BU affiliations across the entire market

### Company List Search
The `find_bu_affiliations.py` script searches a **predefined list** of companies:
- Faster than year range search
- Useful when you know which companies to target
- Edit the `tickers` list in the script to customize

## Features

- **Rate-limited SEC EDGAR API client** - Automatically respects SEC's 10 requests/second limit
- **SQLite caching** - Avoid redundant API calls by caching downloaded filings locally
- **Biography extraction** - Finds biographical sections in proxy statements and 10-Ks
- **NLP-based person extraction** - Uses SpaCy Named Entity Recognition for accurate name extraction
- **Pattern-based fallback** - Works with or without SpaCy installed
- **University affiliation detection** - Identifies degrees, positions, and other affiliations
- **Intelligent context analysis** - Uses dependency parsing to understand relationships
- **Confidence scoring** - Classifies matches as high/medium/low confidence
- **CSV export** - Save search results for further analysis

## Project Structure

- `src/sec_filings/`: Main package code
- `tests/`: Unit tests
- `examples/`: Example scripts
- `data/`: Downloaded filings (gitignored)
- `docs/`: Additional documentation
