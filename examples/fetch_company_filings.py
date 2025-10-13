#!/usr/bin/env python3
"""Example: Fetch and display company filings."""

import sys
from pathlib import Path

# Add src to path for local development
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sec_filings import SECClient


def main():
    # Initialize client with your contact information
    # SEC requires this - replace with your actual info
    client = SECClient(user_agent="Thomas Gardos tgardos@bu.edu")

    # Get CIK for a company (e.g., Apple)
    ticker = "AAPL"
    print(f"Looking up CIK for {ticker}...")
    cik = client.get_cik(ticker)
    print(f"CIK: {cik}\n")

    # Fetch recent 10-K filings
    print("Fetching recent 10-K filings...")
    filings = client.get_filings(cik, filing_type="10-K", count=5)

    print(f"\nFound {len(filings)} filings:\n")
    for i, filing in enumerate(filings, 1):
        print(f"{i}. Type: {filing['type']}")
        print(f"   Date: {filing['date']}")
        print(f"   Accession: {filing['accessionNumber']}")
        print(f"   URL: {filing['url']}\n")

    # Download the most recent filing (optional)
    if filings:
        print("Downloading most recent filing...")
        accession = filings[0]["accessionNumber"]
        output_path = Path(__file__).parent.parent / "data" / f"{ticker}_{accession}.html"
        client.download_filing(accession, str(output_path))
        print(f"Saved to: {output_path}")


if __name__ == "__main__":
    main()
