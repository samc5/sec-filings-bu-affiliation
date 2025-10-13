#!/usr/bin/env python3
"""Search a specific SEC filing for Boston University affiliations.

Usage examples:
  python search_specific_filing.py AAPL DEF14A
  python search_specific_filing.py MSFT 10-K
"""

import sys
from pathlib import Path

# Add src to path for local development
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sec_filings import SECClient, UniversityAffiliationFinder


def main():
    if len(sys.argv) < 2:
        print("Usage: python search_specific_filing.py <TICKER> [FILING_TYPE]")
        print("\nExamples:")
        print("  python search_specific_filing.py AAPL")
        print("  python search_specific_filing.py MSFT DEF14A")
        sys.exit(1)

    ticker = sys.argv[1].upper()
    filing_type = sys.argv[2] if len(sys.argv) > 2 else "DEF 14A"

    # Initialize
    client = SECClient(user_agent="Thomas Gardos tgardos@bu.edu")
    finder = UniversityAffiliationFinder()

    print(f"Searching for Boston University affiliations in {ticker} {filing_type} filings...\n")

    # Get company CIK
    try:
        cik = client.get_cik(ticker)
        print(f"Company: {ticker}")
        print(f"CIK: {cik}\n")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

    # Get most recent filing
    try:
        filings = client.get_filings(cik, filing_type=filing_type, count=1)
        if not filings:
            print(f"No {filing_type} filings found for {ticker}")
            sys.exit(1)

        filing = filings[0]
        print(f"Analyzing {filing['type']} from {filing['date']}")
        print(f"Accession: {filing['accessionNumber']}\n")

    except Exception as e:
        print(f"Error fetching filings: {e}")
        sys.exit(1)

    # Download and search
    try:
        print("Downloading filing...")
        content = client.download_filing(filing["accessionNumber"])

        print("Searching for Boston University mentions...\n")

        filing_metadata = {
            "ticker": ticker,
            "cik": cik,
            "filing_type": filing["type"],
            "date": filing["date"],
            "accession": filing["accessionNumber"],
        }

        matches = finder.search_filing(content, filing_metadata)

        # Display results
        print("=" * 80)
        print("RESULTS")
        print("=" * 80)

        if matches:
            print(f"\nFound {len(matches)} potential Boston University affiliation(s):\n")

            for i, match in enumerate(matches, 1):
                print(f"\n[{i}] {match.person_name}")
                print(f"    Affiliation Type: {match.affiliation_type}")
                print(f"    Confidence: {match.confidence}")
                print(f"    Context:")
                print(f"    {'-' * 76}")
                # Format context nicely
                context_lines = match.context.split("\n")
                for line in context_lines[:10]:  # First 10 lines
                    print(f"    {line.strip()}")
                if len(context_lines) > 10:
                    print(f"    ... ({len(context_lines) - 10} more lines)")
                print()

        else:
            print("\nNo Boston University affiliations found in this filing.")
            print("\nPossible reasons:")
            print("  - No executives/directors have BU affiliation")
            print("  - BU mentioned but not in biographical sections")
            print("  - Biographical sections not properly detected")

    except Exception as e:
        print(f"Error processing filing: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
