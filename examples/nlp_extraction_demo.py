#!/usr/bin/env python3
"""Demo script showing NLP-based extraction vs pattern-based extraction.

This script compares the results of NLP-based (SpaCy) extraction with
traditional pattern-based (regex) extraction.

Usage:
    python nlp_extraction_demo.py AAPL
    python nlp_extraction_demo.py MSFT --filing-type "10-K"
"""

import sys
import argparse
from pathlib import Path

# Add src to path for local development
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sec_filings import (
    SECClient,
    UniversityAffiliationFinder,
    FilingParser,
    BiographyExtractor,
    load_user_agent_from_env,
    is_spacy_available
)


def compare_extraction_methods(ticker: str, filing_type: str = "DEF 14A"):
    """Compare NLP-based vs pattern-based extraction.

    Args:
        ticker: Stock ticker symbol
        filing_type: Type of filing to search
    """
    print("="*80)
    print(f"NLP Extraction Demo: {ticker}")
    print("="*80)

    # Initialize client with caching
    user_agent = load_user_agent_from_env()
    client = SECClient(user_agent=user_agent, use_cache=True)

    try:
        # Get company CIK
        print(f"\n1. Looking up {ticker}...")
        cik = client.get_cik(ticker)
        print(f"   Found CIK: {cik}")

        # Get recent filings
        print(f"\n2. Fetching recent {filing_type} filings...")
        filings = client.get_filings(cik, filing_type=filing_type, count=1)

        if not filings:
            print(f"   No {filing_type} filings found for {ticker}")
            return

        filing = filings[0]
        print(f"   Found: {filing['type']} filed on {filing['date']}")

        # Download filing
        print(f"\n3. Downloading filing...")
        print(f"   Accession: {filing['accessionNumber']}")
        content = client.download_filing(filing["accessionNumber"])
        print(f"   Size: {len(content):,} characters")

        # Check if SpaCy is available
        nlp_available = is_spacy_available()

        if not nlp_available:
            print("\n" + "="*80)
            print("⚠️  SpaCy not available!")
            print("="*80)
            print("Install with: pip install spacy")
            print("Then: python -m spacy download en_core_web_sm")
            print("\nFalling back to pattern-based extraction only...")
            print("="*80)

        # Pattern-based extraction
        print(f"\n4. Pattern-Based Extraction (Regex)")
        print("-" * 80)
        finder_pattern = UniversityAffiliationFinder(use_nlp=False)
        matches_pattern = finder_pattern.search_filing(content)

        print(f"   Found {len(matches_pattern)} match(es)")

        for i, match in enumerate(matches_pattern, 1):
            print(f"\n   Match {i}:")
            print(f"     Person: {match.person_name}")
            print(f"     Type: {match.affiliation_type}")
            print(f"     Confidence: {match.confidence}")
            print(f"     Context: {match.context[:200]}...")

        if not nlp_available:
            return

        # NLP-based extraction
        print(f"\n5. NLP-Based Extraction (SpaCy)")
        print("-" * 80)
        finder_nlp = UniversityAffiliationFinder(use_nlp=True)
        matches_nlp = finder_nlp.search_filing(content)

        print(f"   Found {len(matches_nlp)} match(es)")

        for i, match in enumerate(matches_nlp, 1):
            print(f"\n   Match {i}:")
            print(f"     Person: {match.person_name}")
            print(f"     Type: {match.affiliation_type}")
            print(f"     Confidence: {match.confidence}")
            print(f"     Context: {match.context[:200]}...")

        # Compare results
        print(f"\n6. Comparison")
        print("=" * 80)
        print(f"   Pattern-based: {len(matches_pattern)} match(es)")
        print(f"   NLP-based: {len(matches_nlp)} match(es)")

        # Find unique names in each approach
        pattern_names = set(m.person_name for m in matches_pattern)
        nlp_names = set(m.person_name for m in matches_nlp)

        only_pattern = pattern_names - nlp_names
        only_nlp = nlp_names - pattern_names
        both = pattern_names & nlp_names

        print(f"\n   Names found by both methods: {len(both)}")
        if both:
            for name in sorted(both):
                print(f"     - {name}")

        print(f"\n   Names only found by pattern-based: {len(only_pattern)}")
        if only_pattern:
            for name in sorted(only_pattern):
                print(f"     - {name}")

        print(f"\n   Names only found by NLP-based: {len(only_nlp)}")
        if only_nlp:
            for name in sorted(only_nlp):
                print(f"     - {name}")

        print("\n" + "="*80)
        print("Analysis:")
        print("="*80)
        print("Pattern-based (Regex):")
        print("  + Faster")
        print("  + No dependencies")
        print("  - Higher false positive rate")
        print("  - May miss complex name patterns")
        print()
        print("NLP-based (SpaCy):")
        print("  + More accurate person name detection")
        print("  + Better context understanding")
        print("  + Fewer false positives")
        print("  - Slightly slower")
        print("  - Requires SpaCy installation")
        print("="*80)

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()


def main():
    parser = argparse.ArgumentParser(
        description="Demo NLP-based vs pattern-based extraction"
    )
    parser.add_argument(
        "ticker",
        type=str,
        help="Stock ticker symbol (e.g., AAPL, MSFT)"
    )
    parser.add_argument(
        "--filing-type",
        type=str,
        default="DEF 14A",
        help="Filing type to search (default: 'DEF 14A')"
    )

    args = parser.parse_args()

    compare_extraction_methods(args.ticker, args.filing_type)


if __name__ == "__main__":
    main()
