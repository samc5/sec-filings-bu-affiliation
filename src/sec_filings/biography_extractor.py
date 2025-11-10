"""NLP-based biography and affiliation extractor using SpaCy.

This module provides improved person name extraction and affiliation detection
using Named Entity Recognition (NER) instead of regex patterns.
"""

import re
from typing import List, Dict, Optional, Tuple, Set
from dataclasses import dataclass

try:
    import spacy
    from spacy.tokens import Doc, Span
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False
    print("Warning: SpaCy not available. Install with: pip install spacy")
    print("Then download the model: python -m spacy download en_core_web_sm")


@dataclass
class PersonAffiliation:
    """Structured information about a person's university affiliation.

    Attributes:
        person_name: Full name of the person
        affiliation_type: Type of affiliation (degree, faculty, board, employment, etc.)
        organization: Organization name (e.g., "Boston University")
        degree: Degree earned (e.g., "M.B.A.", "Ph.D.") if applicable
        degree_year: Year degree was earned if mentioned
        position: Position or title at the organization if applicable
        context: Surrounding text that describes the affiliation
        confidence: Confidence level (high, medium, low)
    """
    person_name: str
    affiliation_type: str
    organization: str
    degree: Optional[str] = None
    degree_year: Optional[int] = None
    position: Optional[str] = None
    context: str = ""
    confidence: str = "medium"


class BiographyExtractor:
    """Extract person names and affiliations from biographical text using NLP.

    This class uses SpaCy's Named Entity Recognition (NER) to identify person names,
    then uses dependency parsing and pattern matching to understand their relationships
    with organizations like universities.

    Example:
        >>> extractor = BiographyExtractor()
        >>> text = "John Smith received his M.B.A. from Boston University in 2005."
        >>> affiliations = extractor.extract_affiliations(text, "Boston University")
        >>> print(affiliations[0].person_name)
        'John Smith'
        >>> print(affiliations[0].degree)
        'M.B.A.'
    """

    # Common degree abbreviations
    DEGREE_PATTERNS = [
        r"\b(B\.?A\.?|B\.?S\.?|B\.Sc\.?)\b",  # Bachelor's
        r"\b(M\.?A\.?|M\.?S\.?|M\.Sc\.?|M\.?B\.?A\.?|M\.S\.W\.?|M\.Ed\.?)\b",  # Master's
        r"\b(J\.?D\.?|LL\.?M\.?|LL\.?B\.?)\b",  # Law
        r"\b(M\.?D\.?|D\.?M\.?D\.?)\b",  # Medical
        r"\b(Ph\.?D\.?|D\.?Phil\.?)\b",  # Doctoral
    ]

    # Patterns indicating educational affiliation
    EDUCATION_KEYWORDS = [
        "degree", "graduated", "alumnus", "alumna", "alumni",
        "studied", "attended", "earned", "received", "holds",
        "bachelor", "master", "doctorate", "undergraduate", "graduate"
    ]

    # Patterns indicating employment/position
    POSITION_KEYWORDS = [
        "professor", "faculty", "instructor", "lecturer", "researcher",
        "dean", "president", "chair", "director", "trustee",
        "board member", "fellow", "visiting", "adjunct",
        "taught", "teaches", "appointed", "serves", "served"
    ]

    def __init__(self, model_name: str = "en_core_web_sm"):
        """Initialize the biography extractor.

        Args:
            model_name: SpaCy model to use (default: en_core_web_sm)

        Raises:
            ImportError: If SpaCy is not installed
            OSError: If the specified model is not downloaded
        """
        if not SPACY_AVAILABLE:
            raise ImportError(
                "SpaCy is required for NLP-based extraction. "
                "Install with: pip install spacy && python -m spacy download en_core_web_sm"
            )

        try:
            self.nlp = spacy.load(model_name)
        except OSError:
            raise OSError(
                f"SpaCy model '{model_name}' not found. "
                f"Download with: python -m spacy download {model_name}"
            )

    def extract_person_names(self, text: str) -> List[Dict[str, any]]:
        """Extract person names from text using SpaCy NER.

        Args:
            text: Text to extract names from

        Returns:
            List of dictionaries with 'name', 'start', and 'end' positions
        """
        doc = self.nlp(text)
        persons = []

        for ent in doc.ents:
            if ent.label_ == "PERSON":
                # Filter out likely false positives
                if self._is_valid_person_name(ent.text):
                    persons.append({
                        "name": ent.text,
                        "start": ent.start_char,
                        "end": ent.end_char
                    })

        return persons

    def _is_valid_person_name(self, name: str) -> bool:
        """Check if a name looks like a valid person name.

        Filters out common false positives like company names, acronyms, etc.

        Args:
            name: Name to validate

        Returns:
            True if likely a person name, False otherwise
        """
        # Reject very short names (likely acronyms)
        if len(name) < 4:
            return False

        # Reject if contains common organization keywords
        org_keywords = [
            "corporation", "inc", "llc", "ltd", "company",
            "securities", "exchange", "commission", "university",
            "college", "school", "institute", "department"
        ]
        name_lower = name.lower()
        if any(keyword in name_lower for keyword in org_keywords):
            return False

        # Reject all-caps (likely acronym or header)
        if name.isupper() and len(name) > 3:
            return False

        # Should have at least 2 parts (first and last name)
        parts = name.split()
        if len(parts) < 2:
            return False

        return True

    def extract_affiliations(
        self,
        text: str,
        organization_names: List[str],
        context_window: int = 1000
    ) -> List[PersonAffiliation]:
        """Extract person affiliations with specified organizations.

        Args:
            text: Text to search (e.g., biographical section)
            organization_names: List of organization name variations to search for
                               (e.g., ["Boston University", "BU", "Boston U."])
            context_window: Number of characters before/after org mention to search
                           for person names (default: 500)

        Returns:
            List of PersonAffiliation objects
        """
        affiliations = []

        # Find all mentions of the organization
        org_mentions = self._find_organization_mentions(text, organization_names)

        for org_name, start, end in org_mentions:
            # Get context window around the mention
            context_start = max(0, start - context_window)
            context_end = min(len(text), end + context_window)
            context = text[context_start:context_end]

            # Extract person names from the context
            persons = self.extract_person_names(context)

            # For each person found, analyze the affiliation
            for person in persons:
                # Adjust positions relative to full text
                person_start = context_start + person["start"]
                person_end = context_start + person["end"]

                # Get a focused context around both person and organization
                focused_context = self._get_focused_context(
                    text, person_start, person_end, start, end
                )

                # Analyze the affiliation type
                affiliation = self._analyze_affiliation(
                    person_name=person["name"],
                    organization=org_name,
                    context=focused_context
                )

                if affiliation:
                    affiliations.append(affiliation)

        # Deduplicate by person name
        seen_names = set()
        unique_affiliations = []
        for aff in affiliations:
            if aff.person_name not in seen_names:
                seen_names.add(aff.person_name)
                unique_affiliations.append(aff)

        return unique_affiliations

    def _find_organization_mentions(
        self,
        text: str,
        organization_names: List[str]
    ) -> List[Tuple[str, int, int]]:
        """Find all mentions of organization names in text.

        Args:
            text: Text to search
            organization_names: List of organization name variations

        Returns:
            List of tuples (matched_name, start_position, end_position)
        """
        mentions = []

        for org_name in organization_names:
            # Use case-insensitive search
            pattern = re.compile(re.escape(org_name), re.IGNORECASE)
            for match in pattern.finditer(text):
                mentions.append((org_name, match.start(), match.end()))

        return mentions

    def _get_focused_context(
        self,
        text: str,
        person_start: int,
        person_end: int,
        org_start: int,
        org_end: int,
        window: int = 200
    ) -> str:
        """Get text context that includes both person and organization.

        Args:
            text: Full text
            person_start: Person name start position
            person_end: Person name end position
            org_start: Organization name start position
            org_end: Organization name end position
            window: Additional context window

        Returns:
            Context string
        """
        # Get the range that covers both entities plus window
        start = min(person_start, org_start) - window
        end = max(person_end, org_end) + window

        start = max(0, start)
        end = min(len(text), end)

        return text[start:end]

    def _analyze_affiliation(
        self,
        person_name: str,
        organization: str,
        context: str
    ) -> Optional[PersonAffiliation]:
        """Analyze the context to determine affiliation type and details.

        Args:
            person_name: Name of the person
            organization: Organization name
            context: Text context around the person and organization

        Returns:
            PersonAffiliation object or None if no clear affiliation
        """
        context_lower = context.lower()

        # Look for degree mentions
        degree = self._extract_degree(context)
        degree_year = self._extract_year(context)

        # Determine affiliation type based on keywords
        affiliation_type = "mention"
        confidence = "low"
        position = None

        # Check for degree-related keywords (highest priority)
        if degree or any(keyword in context_lower for keyword in self.EDUCATION_KEYWORDS):
            affiliation_type = "degree" if degree else "education"
            confidence = "high" if degree else "medium"

        # Check for position/employment keywords
        elif any(keyword in context_lower for keyword in self.POSITION_KEYWORDS):
            affiliation_type = "position"
            confidence = "high"
            position = self._extract_position(context)

        # Check for specific patterns using dependency parsing
        doc = self.nlp(context)

        # Look for patterns like "received [degree] from [org]"
        for token in doc:
            if token.lemma_ in ["receive", "earn", "hold", "get"] and token.pos_ == "VERB":
                affiliation_type = "degree"
                confidence = "high"
                break
            elif token.lemma_ in ["teach", "serve", "work"] and token.pos_ == "VERB":
                affiliation_type = "employment"
                confidence = "high"
                break

        return PersonAffiliation(
            person_name=person_name,
            affiliation_type=affiliation_type,
            organization=organization,
            degree=degree,
            degree_year=degree_year,
            position=position,
            context=context,  # Don'tLimit context length
            confidence=confidence
        )

    def _extract_degree(self, text: str) -> Optional[str]:
        """Extract degree abbreviation from text.

        Args:
            text: Text to search

        Returns:
            Degree string (e.g., "M.B.A.") or None
        """
        for pattern in self.DEGREE_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        return None

    def _extract_year(self, text: str) -> Optional[int]:
        """Extract a year (likely graduation year) from text.

        Args:
            text: Text to search

        Returns:
            Year as integer or None
        """
        # Look for 4-digit years between 1950 and 2030
        pattern = r'\b(19[5-9]\d|20[0-3]\d)\b'
        matches = re.findall(pattern, text)

        if matches:
            # Return the first year found
            return int(matches[0])

        return None

    def _extract_position(self, text: str) -> Optional[str]:
        """Extract position/title from text.

        Args:
            text: Text to search

        Returns:
            Position string or None
        """
        # Look for common position titles
        position_pattern = r'\b(professor|dean|chair|director|trustee|fellow|lecturer|instructor)\b'
        match = re.search(position_pattern, text, re.IGNORECASE)

        if match:
            return match.group(1).capitalize()

        return None


def is_spacy_available() -> bool:
    """Check if SpaCy is available and can be used.

    Returns:
        True if SpaCy is installed and a model is available
    """
    if not SPACY_AVAILABLE:
        return False

    try:
        spacy.load("en_core_web_sm")
        return True
    except OSError:
        return False
