"""Parser utilities for extracting information from SEC filings."""

import re
from typing import List, Dict, Optional
from bs4 import BeautifulSoup, Tag


class FilingParser:
    """Parser for extracting structured information from SEC filings."""

    @staticmethod
    def _detect_parser(content: str) -> str:
        """Detect whether content is XML or HTML.

        Args:
            content: File content

        Returns:
            Parser name: "xml" or "lxml" (HTML)
        """
        # Check if content starts with XML declaration or has XML-like structure
        stripped = content.strip()
        if stripped.startswith('<?xml') or stripped.startswith('<XML>'):
            return "xml"
        return "lxml"

    @staticmethod
    def extract_text_from_html(html_content: str) -> str:
        """Extract clean text from HTML filing.

        Args:
            html_content: Raw HTML content

        Returns:
            Clean text with minimal whitespace
        """
        parser = FilingParser._detect_parser(html_content)
        soup = BeautifulSoup(html_content, parser)

        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()

        text = soup.get_text()

        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = " ".join(chunk for chunk in chunks if chunk)

        return text

    @staticmethod
    def find_biographical_sections(html_content: str) -> List[Dict[str, str]]:
        """Find sections containing biographical information about executives/directors.

        Common locations:
        - Proxy statements (DEF 14A): Director and executive officer bios
        - 10-K Item 10: Directors, Executive Officers and Corporate Governance
        - Registration statements (S-1): Management section

        Args:
            html_content: Raw HTML content

        Returns:
            List of dictionaries with 'section_name' and 'content'
        """
        parser = FilingParser._detect_parser(html_content)
        soup = BeautifulSoup(html_content, parser)
        text = soup.get_text()

        sections = []

        # Patterns for biographical sections
        bio_patterns = [
            (r"Item\s+10\.?\s+Directors[,\s]+Executive Officers", "Item 10: Directors & Officers"),
            (r"(?:BOARD OF DIRECTORS|DIRECTORS AND EXECUTIVE OFFICERS)", "Directors & Officers"),
            (r"(?:EXECUTIVE OFFICERS|MANAGEMENT)", "Executive Officers"),
            (r"(?:BIOGRAPHICAL INFORMATION|BIOGRAPHIES)", "Biographies"),
            (r"(?:PROPOSAL\s+\d+[\s\-]+ELECTION OF DIRECTORS)", "Election of Directors"),
        ]

        for pattern, section_name in bio_patterns:
            matches = list(re.finditer(pattern, text, re.IGNORECASE))
            for match in matches:
                start = match.start()
                # Extract a reasonable amount of text (up to 20000 chars or next major section)
                end = min(start + 20000, len(text))

                # Try to find the next "Item" or major section header
                next_section = re.search(
                    r"\n\s*(?:Item\s+\d+|ITEM\s+\d+|PART\s+[IVX]+)",
                    text[start + 100:end],
                    re.IGNORECASE
                )
                if next_section:
                    end = start + 100 + next_section.start()

                content = text[start:end].strip()
                if len(content) > 200:  # Only include substantial sections
                    sections.append({
                        "section_name": section_name,
                        "content": content,
                        "start_position": start
                    })

        # Remove duplicates (overlapping sections)
        unique_sections = []
        seen_positions = set()

        for section in sorted(sections, key=lambda x: x["start_position"]):
            if section["start_position"] not in seen_positions:
                unique_sections.append(section)
                # Mark nearby positions as seen to avoid duplicates
                for i in range(section["start_position"] - 100, section["start_position"] + 100):
                    seen_positions.add(i)

        return unique_sections

    @staticmethod
    def extract_individual_bios(bio_section_text: str) -> List[Dict[str, str]]:
        """Extract individual biographies from a biographical section.

        Args:
            bio_section_text: Text from a biographical section

        Returns:
            List of dictionaries with 'name' and 'bio' for each person
        """
        bios = []

        # Common organization names/keywords to exclude (not people)
        organization_keywords = [
            "stock exchange", "securities", "commission", "corporation",
            "company", "inc.", "llc", "ltd", "limited", "incorporated",
            "new york", "nasdaq", "exchange", "federal", "department",
            "united states", "internal revenue", "financial accounting",
            "table of contents", "form 10", "part i"
        ]

        def is_likely_person_name(name: str) -> bool:
            """Check if name is likely a person (not an organization)."""
            name_lower = name.lower()
            # Check for organization keywords
            for keyword in organization_keywords:
                if keyword in name_lower:
                    return False
            # Reject if all caps (likely section header)
            if name.isupper():
                return False
            # Reject if contains multiple consecutive capitals (NYSE, SEC, etc.)
            if re.search(r"[A-Z]{3,}", name):
                return False
            return True

        # Try multiple patterns to find name+age combinations
        # Pattern 1: Name, age XX or Name (age XX) - most specific
        pattern_with_age = r"(?:^|\n\s*)([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)[,\s]+(?:age\s+)?(\d{2})"

        matches = list(re.finditer(pattern_with_age, bio_section_text, re.MULTILINE))

        for i, match in enumerate(matches):
            name = match.group(1).strip()

            # Skip if not a person name
            if not is_likely_person_name(name):
                continue

            age = match.group(2)
            start = match.start()

            # Find end of this bio (start of next bio or end of section)
            if i + 1 < len(matches):
                end = matches[i + 1].start()
            else:
                end = min(start + 2000, len(bio_section_text))

            bio_text = bio_section_text[start:end].strip()

            bios.append({
                "name": name,
                "age": age,
                "bio": bio_text
            })

        # If no age-based matches, try to find names at paragraph starts
        # Pattern 2: Name followed by title or role (Mr., Ms., Dr., CEO, President, Director, etc.)
        if not bios:
            # Look for names followed by common titles or roles
            name_title_pattern = r"(?:^|\n\s*)([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)[,\s]+(?:Mr\.|Ms\.|Mrs\.|Dr\.|Director|President|CEO|CFO|COO|Chief|Vice|Trustee|has\s+served|is\s+a|serves)"

            matches = list(re.finditer(name_title_pattern, bio_section_text, re.MULTILINE | re.IGNORECASE))

            for i, match in enumerate(matches):
                name = match.group(1).strip()

                # Skip if not a person name
                if not is_likely_person_name(name):
                    continue

                start = match.start()

                # Find end of this bio
                if i + 1 < len(matches):
                    end = matches[i + 1].start()
                else:
                    end = min(start + 2000, len(bio_section_text))

                bio_text = bio_section_text[start:end].strip()

                # Only add if substantial
                if len(bio_text) > 100:
                    bios.append({
                        "name": name,
                        "age": "Unknown",
                        "bio": bio_text
                    })

        # If still no matches, try simpler paragraph-based extraction
        if not bios:
            paragraphs = bio_section_text.split("\n\n")
            for para in paragraphs:
                if len(para) > 100:  # Substantial paragraph
                    # Try to extract a name from the start (First Middle? Last format)
                    first_line = para.split("\n")[0]
                    # More flexible name pattern
                    name_match = re.search(r"([A-Z][a-z]+(?:\s+[A-Z]\.?)?(?:\s+[A-Z][a-z]+)+)", first_line)
                    if name_match:
                        name = name_match.group(1)
                        # Skip if not a person name
                        if is_likely_person_name(name):
                            bios.append({
                                "name": name,
                                "age": "Unknown",
                                "bio": para[:1000]
                            })

        return bios
