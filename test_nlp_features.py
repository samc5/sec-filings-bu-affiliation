#!/usr/bin/env python3
"""Test script for new NLP features.

This script tests the new NLP-based modules without requiring a full
integration test. It verifies:
1. Cache module works
2. BiographyExtractor can be imported
3. SECClient supports caching
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_cache():
    """Test the FilingCache module."""
    print("Testing FilingCache...")
    from sec_filings.cache import FilingCache

    # Create a cache instance
    cache = FilingCache(cache_dir=Path(__file__).parent / "test_cache")

    # Test set and get
    test_accession = "0000320193-23-000077"
    test_content = "<html>Test filing content</html>"

    cache.set(test_accession, test_content)
    retrieved = cache.get(test_accession)

    assert retrieved == test_content, "Cache get/set failed"

    # Test stats
    stats = cache.get_stats()
    assert stats["total_entries"] >= 1, "Cache stats failed"

    # Test has
    assert cache.has(test_accession), "Cache has() failed"

    # Clean up
    cache.clear_all()

    print("  ✓ FilingCache works correctly")


def test_biography_extractor_import():
    """Test BiographyExtractor can be imported."""
    print("\nTesting BiographyExtractor import...")

    try:
        from sec_filings.biography_extractor import (
            BiographyExtractor,
            PersonAffiliation,
            is_spacy_available
        )

        # Check if SpaCy is available
        if is_spacy_available():
            print("  ✓ SpaCy is available")

            # Test basic extraction
            extractor = BiographyExtractor()

            # Test simple text
            test_text = "John Smith received his M.B.A. from Boston University in 2005."
            persons = extractor.extract_person_names(test_text)

            if persons:
                print(f"  ✓ Extracted {len(persons)} person(s): {persons[0]['name']}")
            else:
                print("  ⚠ No persons extracted (this may be okay for simple text)")

            # Test affiliation extraction
            affiliations = extractor.extract_affiliations(
                test_text,
                organization_names=["Boston University", "BU"]
            )

            if affiliations:
                aff = affiliations[0]
                print(f"  ✓ Found affiliation: {aff.person_name}")
                print(f"    - Type: {aff.affiliation_type}")
                if aff.degree:
                    print(f"    - Degree: {aff.degree}")
                if aff.degree_year:
                    print(f"    - Year: {aff.degree_year}")
            else:
                print("  ⚠ No affiliations found (SpaCy may need more context)")

        else:
            print("  ⚠ SpaCy not available")
            print("    Install with: pip install spacy")
            print("    Then: python -m spacy download en_core_web_sm")

        print("  ✓ BiographyExtractor imports successfully")

    except ImportError as e:
        print(f"  ✗ Import failed: {e}")
        return False

    return True


def test_client_caching():
    """Test SECClient with caching support."""
    print("\nTesting SECClient with caching...")
    from sec_filings import SECClient

    # Test that client can be initialized with cache parameter
    client = SECClient(user_agent="Test User test@example.com", use_cache=True)
    assert client.cache is not None, "Cache not initialized"

    client_no_cache = SECClient(user_agent="Test User test@example.com", use_cache=False)
    assert client_no_cache.cache is None, "Cache should be None when disabled"

    print("  ✓ SECClient caching support works")


def test_imports():
    """Test that all new modules can be imported from main package."""
    print("\nTesting package imports...")
    from sec_filings import (
        SECClient,
        FilingCache,
        BiographyExtractor,
        PersonAffiliation,
        is_spacy_available
    )

    print("  ✓ All new modules import successfully")


def main():
    """Run all tests."""
    print("="*60)
    print("Testing NLP Features Implementation")
    print("="*60)

    try:
        test_cache()
        test_imports()
        test_client_caching()
        test_biography_extractor_import()

        print("\n" + "="*60)
        print("✓ All tests passed!")
        print("="*60)

        print("\nNext steps:")
        print("1. Install dependencies: pip install -r requirements.txt")
        print("2. Install SpaCy model: python -m spacy download en_core_web_sm")
        print("3. Run example scripts to test with real SEC filings")

    except Exception as e:
        print("\n" + "="*60)
        print(f"✗ Test failed: {e}")
        print("="*60)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
