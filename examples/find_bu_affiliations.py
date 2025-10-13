#!/usr/bin/env python3
"""Find all Boston University affiliations in SEC filings.

This script searches SEC filings (particularly proxy statements and 10-Ks)
for mentions of Boston University in executive and director biographies.
"""

import sys
import csv
from pathlib import Path
from typing import List

# Add src to path for local development
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sec_filings import SECClient, UniversityAffiliationFinder, AffiliationMatch, load_user_agent_from_env


def search_company_filings(
    client: SECClient,
    finder: UniversityAffiliationFinder,
    ticker: str,
    filing_types: List[str] = ["DEF 14A", "10-K"],
    max_filings: int = 5
) -> List[AffiliationMatch]:
    """Search filings for a single company.

    Args:
        client: SEC API client
        finder: University affiliation finder
        ticker: Company ticker symbol
        filing_types: Types of filings to search (DEF 14A = proxy statements)
        max_filings: Maximum number of filings to search per type

    Returns:
        List of affiliation matches found
    """
    print(f"\n{'=' * 80}")
    print(f"Searching: {ticker}")
    print(f"{'=' * 80}")

    try:
        cik = client.get_cik(ticker)
        print(f"CIK: {cik}")
    except Exception as e:
        print(f"Error getting CIK: {e}")
        return []

    all_matches = []

    for filing_type in filing_types:
        print(f"\nFetching {filing_type} filings...")
        try:
            filings = client.get_filings(cik, filing_type=filing_type, count=max_filings)
            print(f"Found {len(filings)} filings")

            for i, filing in enumerate(filings, 1):
                print(f"\n  [{i}/{len(filings)}] Processing {filing['date']}...")

                try:
                    # Download filing content
                    content = client.download_filing(filing["accessionNumber"])

                    # Search for affiliations
                    filing_metadata = {
                        "ticker": ticker,
                        "cik": cik,
                        "filing_type": filing["type"],
                        "date": filing["date"],
                        "accession": filing["accessionNumber"],
                    }

                    matches = finder.search_filing(content, filing_metadata)

                    if matches:
                        print(f"    ✓ Found {len(matches)} potential matches!")
                        all_matches.extend(matches)
                    else:
                        print(f"    - No matches found")

                except Exception as e:
                    print(f"    ✗ Error processing filing: {e}")

        except Exception as e:
            print(f"Error fetching {filing_type} filings: {e}")

    return all_matches


def save_results_to_csv(matches: List[AffiliationMatch], output_path: Path):
    """Save affiliation matches to CSV file.

    Args:
        matches: List of affiliation matches
        output_path: Path to output CSV file
    """
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Ticker",
            "Person Name",
            "Filing Type",
            "Filing Date",
            "Accession Number",
            "Affiliation Type",
            "Confidence",
            "Context"
        ])

        for match in matches:
            filing_info = match.filing_info or {}
            writer.writerow([
                filing_info.get("ticker", ""),
                match.person_name,
                filing_info.get("filing_type", ""),
                filing_info.get("date", ""),
                filing_info.get("accession", ""),
                match.affiliation_type,
                match.confidence,
                match.context[:500]  # Truncate long contexts
            ])

    print(f"\n✓ Results saved to: {output_path}")


def main():
    # Initialize client and finder
    user_agent = load_user_agent_from_env()
    client = SECClient(user_agent=user_agent)
    finder = UniversityAffiliationFinder()  # Defaults to Boston University

    # Companies to search (modify this list as needed)
    tickers = [
        "AAPL",   # Apple
        "MSFT",   # Microsoft
        "GOOGL",  # Alphabet
        "AMZN",   # Amazon
        "META",   # Meta
        # Add more companies here
    ]

    print("Boston University Affiliation Search")
    print("=" * 80)
    print(f"Searching {len(tickers)} companies for BU affiliations...")
    print("\nNote: This searches proxy statements (DEF 14A) and 10-K filings")
    print("which typically contain executive and director biographies.\n")

    all_matches = []

    for ticker in tickers:
        matches = search_company_filings(
            client=client,
            finder=finder,
            ticker=ticker,
            filing_types=["DEF 14A", "10-K"],
            max_filings=3  # Search last 3 filings of each type
        )
        all_matches.extend(matches)

    # Deduplicate matches
    unique_matches = UniversityAffiliationFinder.deduplicate_matches(all_matches)

    # Display results
    print("\n" + "=" * 80)
    print("RESULTS SUMMARY")
    print("=" * 80)
    print(f"Total matches found: {len(all_matches)}")
    print(f"Unique matches: {len(unique_matches)}")

    if unique_matches:
        print("\nMatches by confidence level:")
        for confidence in ["high", "medium", "low"]:
            count = sum(1 for m in unique_matches if m.confidence == confidence)
            if count > 0:
                print(f"  {confidence.upper()}: {count}")

        print("\n" + "-" * 80)
        print("Detailed Results:")
        print("-" * 80)

        for match in unique_matches:
            filing_info = match.filing_info or {}
            print(f"\n{match.person_name} [{match.confidence} confidence]")
            print(f"  Company: {filing_info.get('ticker', 'Unknown')}")
            print(f"  Filing: {filing_info.get('filing_type', '')} from {filing_info.get('date', '')}")
            print(f"  Affiliation: {match.affiliation_type}")
            print(f"  Context: {match.context[:200]}...")

        # Save to CSV
        output_path = Path(__file__).parent.parent / "data" / "bu_affiliations.csv"
        save_results_to_csv(unique_matches, output_path)

    else:
        print("\nNo Boston University affiliations found in searched filings.")
        print("Consider:")
        print("  - Searching more companies")
        print("  - Increasing max_filings parameter")
        print("  - Checking different filing types")


if __name__ == "__main__":
    main()
