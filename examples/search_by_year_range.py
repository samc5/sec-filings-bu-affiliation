#!/usr/bin/env python3
"""Search all SEC filings by year range for Boston University affiliations.

This script searches across ALL companies that filed with the SEC during
a specified time period, rather than limiting to a predefined list of companies.

Usage:
    python search_by_year_range.py --start-year 2020 --end-year 2024
    python search_by_year_range.py --start-year 2023 --end-year 2023 --filing-types "DEF 14A"
"""

import sys
import csv
import argparse
from pathlib import Path
from datetime import datetime

# Add src to path for local development
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sec_filings import (
    SECClient,
    UniversityAffiliationFinder,
    AffiliationMatch,
    load_user_agent_from_env,
    is_spacy_available
)

# Try to import tqdm for progress bars
try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False
    print("Note: Install tqdm for progress bars: pip install tqdm")


def search_filings_with_progress(
    client: SECClient,
    finder: UniversityAffiliationFinder,
    filings: list,
    batch_size: int = 50,
    save_interval: int = 100,
    output_path: Path = None,
    use_progress_bar: bool = True,
) -> list:
    """Search filings for BU affiliations with progress tracking and periodic saves.

    Args:
        client: SEC API client
        finder: University affiliation finder
        filings: List of filings to search
        batch_size: Number of filings to process before showing progress
        save_interval: Number of matches before saving to disk
        output_path: Path to save results
        use_progress_bar: Whether to use tqdm progress bar (default: True)

    Returns:
        List of all affiliation matches found
    """
    all_matches = []
    processed = 0
    errors = 0

    print(f"\nSearching {len(filings)} filings for Boston University affiliations...")

    # Use tqdm progress bar if available and requested
    if TQDM_AVAILABLE and use_progress_bar:
        filings_iter = tqdm(filings, desc="Processing filings", unit="filing")
    else:
        filings_iter = filings
        print(f"Progress will be shown every {batch_size} filings.\n")

    for i, filing in enumerate(filings_iter, 1):
        try:
            # Download filing
            content = client.download_filing(filing["accessionNumber"])

            # Search for affiliations
            matches = finder.search_filing(content, filing_metadata=filing)

            if matches:
                match_msg = f"✓ {filing['company_name']} ({filing['ticker']}) {filing['type']} {filing['date']}: Found {len(matches)} match(es)!"
                if TQDM_AVAILABLE and use_progress_bar:
                    tqdm.write(f"  {match_msg}")
                else:
                    print(f"  [{i}/{len(filings)}] {match_msg}")
                all_matches.extend(matches)

                # Save periodically
                if output_path and len(all_matches) % save_interval == 0:
                    save_results_to_csv(all_matches, output_path)
                    save_msg = f"→ Saved {len(all_matches)} matches to disk"
                    if TQDM_AVAILABLE and use_progress_bar:
                        tqdm.write(f"    {save_msg}")
                    else:
                        print(f"    {save_msg}")

            processed += 1

            # Show periodic progress (only if not using progress bar)
            if not (TQDM_AVAILABLE and use_progress_bar) and i % batch_size == 0:
                print(f"\nProgress: {i}/{len(filings)} filings processed "
                      f"({100*i/len(filings):.1f}%)")
                print(f"  Matches found: {len(all_matches)}")
                print(f"  Errors: {errors}\n")

        except Exception as e:
            errors += 1
            # Always print error details
            error_msg = f"✗ Error processing {filing.get('company_name', 'Unknown')} ({filing.get('ticker', '')}): {str(e)[:80]}"
            if TQDM_AVAILABLE and use_progress_bar:
                tqdm.write(f"  {error_msg}")
            else:
                print(f"  [{i}/{len(filings)}] {error_msg}")

    print(f"\n{'='*80}")
    print(f"Search complete!")
    print(f"  Total filings processed: {processed}/{len(filings)}")
    print(f"  Total matches found: {len(all_matches)}")
    print(f"  Total errors: {errors}")
    print(f"{'='*80}\n")

    return all_matches


def save_results_to_csv(matches: list, output_path: Path):
    """Save affiliation matches to CSV file.

    Args:
        matches: List of affiliation matches
        output_path: Path to output CSV file
    """
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Company Name",
            "Ticker",
            "CIK",
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
                filing_info.get("company_name", ""),
                filing_info.get("ticker", ""),
                filing_info.get("cik", ""),
                match.person_name,
                filing_info.get("type", ""),
                filing_info.get("date", ""),
                filing_info.get("accessionNumber", ""),
                match.affiliation_type,
                match.confidence,
                match.context[:500]  # Truncate long contexts
            ])


def main():
    parser = argparse.ArgumentParser(
        description="Search SEC filings by year range for Boston University affiliations"
    )
    parser.add_argument(
        "--start-year",
        type=int,
        required=True,
        help="Start year (e.g., 2020)"
    )
    parser.add_argument(
        "--end-year",
        type=int,
        required=True,
        help="End year (e.g., 2024)"
    )
    parser.add_argument(
        "--filing-types",
        type=str,
        default="DEF 14A,10-K",
        help="Comma-separated filing types (default: 'DEF 14A,10-K')"
    )
    parser.add_argument(
        "--max-per-company",
        type=int,
        default=1,
        help="Maximum filings to fetch per company (default: 1)"
    )
    parser.add_argument(
        "--test-mode",
        action="store_true",
        help="Test mode: only search first 50 companies"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output CSV file path (default: data/bu_affiliations_YYYY-MM-DD.csv)"
    )
    parser.add_argument(
        "--use-nlp",
        action="store_true",
        help="Use NLP-based extraction with SpaCy (more accurate, requires SpaCy installation)"
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable filing cache (downloads will not be cached)"
    )
    parser.add_argument(
        "--no-progress-bar",
        action="store_true",
        help="Disable tqdm progress bar"
    )

    args = parser.parse_args()

    # Validate years
    current_year = datetime.now().year
    if args.start_year > args.end_year:
        print("Error: start-year must be <= end-year")
        sys.exit(1)
    if args.end_year > current_year:
        print(f"Warning: end-year {args.end_year} is in the future. Using {current_year} instead.")
        args.end_year = current_year

    # Parse filing types
    filing_types = [ft.strip() for ft in args.filing_types.split(",")]

    # Set up output path
    if args.output:
        output_path = Path(args.output)
    else:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        output_path = Path(__file__).parent.parent / "data" / f"bu_affiliations_{timestamp}.csv"

    output_path.parent.mkdir(exist_ok=True)

    print("="*80)
    print("SEC Filings Search by Year Range")
    print("="*80)

    # Check NLP availability
    nlp_available = is_spacy_available()
    use_nlp = args.use_nlp and nlp_available

    if args.use_nlp and not nlp_available:
        print("WARNING: --use-nlp requested but SpaCy not available!")
        print("Install with: pip install spacy")
        print("Then: python -m spacy download en_core_web_sm")
        print("Falling back to pattern-based extraction.\n")

    print(f"Search Parameters:")
    print(f"  Year Range: {args.start_year} - {args.end_year}")
    print(f"  Filing Types: {', '.join(filing_types)}")
    print(f"  Max per company: {args.max_per_company}")
    print(f"  Test Mode: {'YES (50 companies only)' if args.test_mode else 'NO (all companies)'}")
    print(f"  Extraction Method: {'NLP-based (SpaCy)' if use_nlp else 'Pattern-based (regex)'}")
    print(f"  Caching: {'Enabled' if not args.no_cache else 'Disabled'}")
    print(f"  Progress Bar: {'Enabled (tqdm)' if (TQDM_AVAILABLE and not args.no_progress_bar) else 'Disabled'}")
    print(f"  Output: {output_path}")
    print("="*80)

    # Initialize client and finder
    user_agent = load_user_agent_from_env()
    client = SECClient(user_agent=user_agent, use_cache=not args.no_cache)
    finder = UniversityAffiliationFinder(use_nlp=use_nlp)

    # Show cache stats if enabled
    if not args.no_cache and client.cache:
        stats = client.cache.get_stats()
        if stats['total_entries'] > 0:
            print(f"\nCache Statistics:")
            print(f"  Cached filings: {stats['total_entries']}")
            print(f"  Cache size: {stats['total_size_mb']} MB")
            print(f"  Oldest entry: {stats['oldest_entry_days']} days old")

    # Convert years to date strings
    start_date = f"{args.start_year}-01-01"
    end_date = f"{args.end_year}-12-31"

    # Fetch filings for all companies
    print("\nStep 1: Fetching filings across all companies...")
    print(f"Note: This will search all ~13,000 public companies in the SEC database.")
    print(f"This step alone may take 10-30 minutes depending on parameters.\n")

    try:
        filings = client.get_recent_filings_bulk(
            filing_types=filing_types,
            start_date=start_date,
            end_date=end_date,
            max_per_company=args.max_per_company,
            company_limit=50 if args.test_mode else None,
        )

        if not filings:
            print("\nNo filings found for the specified parameters.")
            print("Try:")
            print("  - Expanding the year range")
            print("  - Adding more filing types")
            sys.exit(0)

        print(f"\nStep 2: Searching {len(filings)} filings for Boston University mentions...")

        # Search each filing
        matches = search_filings_with_progress(
            client=client,
            finder=finder,
            filings=filings,
            batch_size=50,
            save_interval=100,
            output_path=output_path,
            use_progress_bar=not args.no_progress_bar,
        )

        # Deduplicate
        unique_matches = UniversityAffiliationFinder.deduplicate_matches(matches)

        # Final save
        save_results_to_csv(unique_matches, output_path)
        print(f"✓ Final results saved to: {output_path}")

        # Summary statistics
        print("\n" + "="*80)
        print("SUMMARY")
        print("="*80)
        print(f"Total unique matches: {len(unique_matches)}")

        if unique_matches:
            print("\nBy confidence level:")
            for confidence in ["high", "medium", "low"]:
                count = sum(1 for m in unique_matches if m.confidence == confidence)
                if count > 0:
                    print(f"  {confidence.upper()}: {count}")

            print("\nBy affiliation type:")
            type_counts = {}
            for m in unique_matches:
                type_counts[m.affiliation_type] = type_counts.get(m.affiliation_type, 0) + 1
            for aff_type, count in sorted(type_counts.items(), key=lambda x: -x[1]):
                print(f"  {aff_type}: {count}")

            print(f"\nTop companies with BU affiliations:")
            company_counts = {}
            for m in unique_matches:
                company = m.filing_info.get("company_name", "Unknown")
                company_counts[company] = company_counts.get(company, 0) + 1
            for company, count in sorted(company_counts.items(), key=lambda x: -x[1])[:10]:
                print(f"  {company}: {count}")

    except KeyboardInterrupt:
        print("\n\nSearch interrupted by user.")
        if all_matches:
            print(f"Saving {len(all_matches)} matches found so far...")
            save_results_to_csv(all_matches, output_path)
            print(f"✓ Partial results saved to: {output_path}")
        sys.exit(0)

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
