# SEC Filings Research

A Python toolkit for downloading and analyzing SEC filings from the EDGAR database.

## Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Usage

```python
from sec_filings import SECClient

# Initialize client with your contact info (required by SEC)
client = SECClient(user_agent="Your Name your.email@example.com")

# Get company CIK (Central Index Key)
cik = client.get_cik("AAPL")

# Fetch recent filings
filings = client.get_filings(cik, filing_type="10-K", count=5)

# Download a specific filing
filing_data = client.download_filing(filings[0]["accessionNumber"])
```

## Examples

See the `examples/` directory for sample scripts:
- `fetch_company_filings.py`: Download filings for a specific company
- `parse_10k.py`: Extract sections from 10-K filings

## Project Structure

- `src/sec_filings/`: Main package code
- `tests/`: Unit tests
- `examples/`: Example scripts
- `data/`: Downloaded filings (gitignored)
- `docs/`: Additional documentation
