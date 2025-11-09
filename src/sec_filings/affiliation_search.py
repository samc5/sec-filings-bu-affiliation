"""Search for university and institutional affiliations in SEC filings."""

import re
from typing import List, Dict, Set, Optional
from dataclasses import dataclass

from .parser import FilingParser


@dataclass
class AffiliationMatch:
    """Represents a found affiliation match."""
    person_name: str
    affiliation_type: str  # e.g., "degree", "faculty", "trustee", "board"
    context: str  # Surrounding text
    confidence: str  # "high", "medium", "low"
    filing_info: Optional[Dict[str, str]] = None


class UniversityAffiliationFinder:
    """Find mentions of university affiliations in biographical text."""

    # Boston University variations - full names only to avoid false positives
    BU_PATTERNS = [
        r"Boston\s+University",
        r"Boston\s+U\.",
        r"\s+BU\s+",
        r"\s+B\.\s*U\.\s"
    ]

    # Degree patterns
    DEGREE_PATTERNS = [
        r"(?:B\.?A\.?|Bachelor(?:'s)?|B\.?S\.?|Master(?:'s)?|M\.?A\.?|M\.?B\.?A\.?|M\.?S\.?|"
        r"Ph\.?D\.?|J\.?D\.?|M\.?D\.?|LL\.?M\.?|LL\.?B\.?|Ed\.?D\.?)",
    ]

    # Role/position patterns
    ROLE_PATTERNS = [
        r"professor",
        r"faculty",
        r"instructor",
        r"lecturer",
        r"researcher",
        r"fellow",
        r"trustee",
        r"board member",
        r"dean",
        r"chair",
        r"president",
        r"chancellor",
        r"provost",
    ]

    def __init__(
        self,
        university_patterns: Optional[List[str]] = None,
        use_nlp: bool = True
    ):
        """Initialize affiliation finder.

        Args:
            university_patterns: Custom university name patterns. Defaults to Boston University.
            use_nlp: Whether to use NLP-based extraction if available (default: True)
        """
        self.university_patterns = university_patterns or self.BU_PATTERNS
        self.use_nlp = use_nlp

        # Try to initialize BiographyExtractor if NLP is requested
        self.nlp_extractor = None
        if use_nlp:
            try:
                from .biography_extractor import BiographyExtractor, is_spacy_available
                if is_spacy_available():
                    self.nlp_extractor = BiographyExtractor()
            except ImportError:
                pass  # Fall back to pattern-based

    def find_affiliations_in_text(
        self,
        text: str,
        person_name: Optional[str] = None
    ) -> List[AffiliationMatch]:
        """Find university affiliations in text.

        Args:
            text: Text to search (e.g., biography)
            person_name: Name of person (if known)

        Returns:
            List of affiliation matches
        """
        matches = []

        # Create regex pattern combining university and context
        for uni_pattern in self.university_patterns:
            # Find all mentions of the university (case-insensitive)
            for uni_match in re.finditer(uni_pattern, text, re.IGNORECASE):
                # Extract context around the mention (±1500 chars)
                start = max(0, uni_match.start() - 1500)
                end = min(len(text), uni_match.end() + 1500)
                context = text[start:end]

                # Determine affiliation type and confidence
                affiliation_type, confidence = self._classify_affiliation(context)

                if affiliation_type:
                    matches.append(AffiliationMatch(
                        person_name=person_name or "Unknown",
                        affiliation_type=affiliation_type,
                        context=context.strip(),
                        confidence=confidence
                    ))

        return matches

    def _classify_affiliation(self, context: str) -> tuple[Optional[str], str]:
        """Classify the type of affiliation based on context.

        Args:
            context: Text context around university mention

        Returns:
            Tuple of (affiliation_type, confidence_level)
        """
        context_lower = context.lower()

        # Check for degrees
        for degree_pattern in self.DEGREE_PATTERNS:
            if re.search(degree_pattern, context, re.IGNORECASE):
                return ("degree", "high")

        # Check for roles/positions
        for role_pattern in self.ROLE_PATTERNS:
            if re.search(role_pattern, context_lower):
                return ("position", "high")

        # Check for generic education/employment keywords
        education_keywords = ["studied", "attended", "graduated", "alumnus", "alumni", "educated"]
        employment_keywords = ["served", "worked", "employed", "appointed", "joined"]

        for keyword in education_keywords:
            if keyword in context_lower:
                return ("education", "medium")

        for keyword in employment_keywords:
            if keyword in context_lower:
                return ("employment", "medium")

        # If university mentioned but no clear context
        return ("mention", "low")

    def find_affiliations_nlp(
        self,
        text: str,
        organization_names: Optional[List[str]] = None,
        context_window: int = 1500
    ) -> List[AffiliationMatch]:
        """Find affiliations using NLP-based extraction.

        This method uses SpaCy NER if available, otherwise falls back to
        pattern-based extraction.

        Args:
            text: Text to search
            organization_names: List of organization name variations
            context_window: Context window size for extraction

        Returns:
            List of AffiliationMatch objects
        """
        if self.nlp_extractor is None:
            # Fall back to pattern-based
            return self.find_affiliations_in_text(text)

        # Use organization names if provided, otherwise use configured patterns
        if organization_names is None:
            # Convert regex patterns to plain strings for NLP extractor
            organization_names = []
            for pattern in self.university_patterns:
                # Remove regex escapes and convert to plain text
                name = pattern.replace(r"\s+", " ").replace(r"\.", ".")
                organization_names.append(name)

        # Extract affiliations using NLP
        from .biography_extractor import PersonAffiliation
        nlp_affiliations = self.nlp_extractor.extract_affiliations(
            text,
            organization_names=organization_names,
            context_window=context_window
        )

        # Convert PersonAffiliation objects to AffiliationMatch objects
        matches = []
        for aff in nlp_affiliations:
            matches.append(AffiliationMatch(
                person_name=aff.person_name,
                affiliation_type=aff.affiliation_type,
                context=aff.context,
                confidence=aff.confidence,
                filing_info=None
            ))

        return matches

    def search_filing(
        self,
        html_content: str,
        filing_metadata: Optional[Dict[str, str]] = None,
        use_enhanced_parser: bool = True
    ) -> List[AffiliationMatch]:
        """Search an entire SEC filing for university affiliations.

        Args:
            html_content: Raw HTML content of filing
            filing_metadata: Optional metadata about the filing (ticker, date, type, etc.)
            use_enhanced_parser: Whether to use enhanced parser (default: True)

        Returns:
            List of all affiliation matches found
        """
        parser = FilingParser()
        all_matches = []

        # Use enhanced parser if requested and NLP is available
        if use_enhanced_parser and self.nlp_extractor is not None:
            bio_sections = parser.find_biographical_sections_enhanced(html_content)
        else:
            bio_sections = parser.find_biographical_sections(html_content)

        for section in bio_sections:
            # Use NLP-based extraction if available
            if self.nlp_extractor is not None:
                # Use NLP to find affiliations directly
                matches = self.find_affiliations_nlp(section["content"])
                for match in matches:
                    match.filing_info = filing_metadata
                all_matches.extend(matches)
            else:
                # Fall back to pattern-based extraction
                # Extract individual biographies
                individual_bios = parser.extract_individual_bios(section["content"])

                if individual_bios:
                    # Search each individual bio
                    for bio in individual_bios:
                        matches = self.find_affiliations_in_text(
                            bio["bio"],
                            person_name=bio["name"]
                        )
                        for match in matches:
                            match.filing_info = filing_metadata
                        all_matches.extend(matches)
                else:
                    # No individual bios found, search entire section
                    matches = self.find_affiliations_in_text(section["content"])
                    for match in matches:
                        match.filing_info = filing_metadata
                    all_matches.extend(matches)

        return all_matches

    @staticmethod
    def deduplicate_matches(matches: List[AffiliationMatch]) -> List[AffiliationMatch]:
        """Remove duplicate or very similar matches.

        Args:
            matches: List of affiliation matches

        Returns:
            Deduplicated list
        """
        seen = set()
        unique_matches = []

        for match in matches:
            # Create a key based on person name and context snippet
            key = (
                match.person_name.lower().strip(),
                match.context[:100].lower().strip()
            )

            if key not in seen:
                seen.add(key)
                unique_matches.append(match)

        return unique_matches
