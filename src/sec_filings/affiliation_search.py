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

    # Boston University variations and common abbreviations
    BU_PATTERNS = [
        r"Boston\s+University",
        r"\bBU\b",
        r"Boston\s+U\.",
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

    def __init__(self, university_patterns: Optional[List[str]] = None):
        """Initialize affiliation finder.

        Args:
            university_patterns: Custom university name patterns. Defaults to Boston University.
        """
        self.university_patterns = university_patterns or self.BU_PATTERNS

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
            # Find all mentions of the university
            for uni_match in re.finditer(uni_pattern, text, re.IGNORECASE):
                # Extract context around the mention (±200 chars)
                start = max(0, uni_match.start() - 200)
                end = min(len(text), uni_match.end() + 200)
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

    def search_filing(
        self,
        html_content: str,
        filing_metadata: Optional[Dict[str, str]] = None
    ) -> List[AffiliationMatch]:
        """Search an entire SEC filing for university affiliations.

        Args:
            html_content: Raw HTML content of filing
            filing_metadata: Optional metadata about the filing (ticker, date, type, etc.)

        Returns:
            List of all affiliation matches found
        """
        parser = FilingParser()
        all_matches = []

        # Find biographical sections
        bio_sections = parser.find_biographical_sections(html_content)

        for section in bio_sections:
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
