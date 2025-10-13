#!/usr/bin/env python3
"""Example: Parse sections from a 10-K filing."""

import sys
import re
from pathlib import Path
from bs4 import BeautifulSoup

# Add src to path for local development
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sec_filings import SECClient


def extract_10k_sections(html_content: str) -> dict:
    """Extract common sections from a 10-K filing.

    Common sections include:
    - Item 1: Business
    - Item 1A: Risk Factors
    - Item 7: Management's Discussion and Analysis
    - Item 8: Financial Statements
    """
    soup = BeautifulSoup(html_content, "lxml")
    text = soup.get_text()

    sections = {}

    # Simple pattern matching for section headers
    # Note: This is a basic example. Real 10-Ks have varied formatting.
    patterns = {
        "business": r"Item\s+1\.?\s+Business",
        "risk_factors": r"Item\s+1A\.?\s+Risk Factors",
        "md_and_a": r"Item\s+7\.?\s+Management'?s Discussion and Analysis",
        "financial_statements": r"Item\s+8\.?\s+Financial Statements",
    }

    for key, pattern in patterns.items():
        matches = list(re.finditer(pattern, text, re.IGNORECASE))
        if matches:
            start = matches[0].start()
            # Find the next section or use a reasonable length
            end = start + 5000  # First 5000 chars as preview
            sections[key] = text[start:end].strip()

    return sections


def main():
    # Initialize client
    client = SECClient(user_agent="Your Name your.email@example.com")

    # Get a 10-K filing
    ticker = "AAPL"
    cik = client.get_cik(ticker)
    filings = client.get_filings(cik, filing_type="10-K", count=1)

    if not filings:
        print("No 10-K filings found")
        return

    # Download the filing
    print(f"Downloading 10-K from {filings[0]['date']}...")
    content = client.download_filing(filings[0]["accessionNumber"])

    # Extract sections
    print("\nExtracting sections...")
    sections = extract_10k_sections(content)

    # Display results
    for section_name, section_content in sections.items():
        print(f"\n{'=' * 80}")
        print(f"SECTION: {section_name.upper()}")
        print(f"{'=' * 80}")
        print(section_content[:500] + "..." if len(section_content) > 500 else section_content)


if __name__ == "__main__":
    main()
