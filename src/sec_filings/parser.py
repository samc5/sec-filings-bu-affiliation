"""Parser utilities for extracting information from SEC filings."""

import re
from typing import List, Dict, Optional
from bs4 import BeautifulSoup, Tag


class FilingParser:
    """Parser for extracting structured information from SEC filings."""

    @staticmethod
    def extract_text_from_html(html_content: str) -> str:
        """Extract clean text from HTML filing.

        Args:
            html_content: Raw HTML content

        Returns:
            Clean text with minimal whitespace
        """
        soup = BeautifulSoup(html_content, "lxml")

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
        soup = BeautifulSoup(html_content, "lxml")
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

        # Pattern to find names (often in bold/caps at start of paragraph)
        # Looks for: Name, age XX, or Name (age XX) or just capitalized name patterns
        name_pattern = r"(?:^|\n\s*)([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)[,\s]+(?:age\s+)?(\d{2})"

        matches = list(re.finditer(name_pattern, bio_section_text, re.MULTILINE))

        for i, match in enumerate(matches):
            name = match.group(1).strip()
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

        # If no structured bios found, try simpler paragraph-based extraction
        if not bios:
            paragraphs = bio_section_text.split("\n\n")
            for para in paragraphs:
                if len(para) > 100:  # Substantial paragraph
                    # Try to extract a name from the start
                    first_line = para.split("\n")[0]
                    name_match = re.search(r"([A-Z][a-z]+\s+[A-Z]\.?\s+[A-Z][a-z]+)", first_line)
                    if name_match:
                        bios.append({
                            "name": name_match.group(1),
                            "age": "Unknown",
                            "bio": para[:1000]
                        })

        return bios
