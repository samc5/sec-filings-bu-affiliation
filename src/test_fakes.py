"""
SEC Filings Parser - Run both NLP and pattern-based parsers on specific files
"""
import os
import csv
from pathlib import Path
from datetime import datetime

from sec_filings import (
    SECClient,
    UniversityAffiliationFinder,
    BiographyExtractor,
    FilingParser,
    load_user_agent_from_env,
    is_spacy_available
)
from openai import AzureOpenAI
import json
from dotenv import load_dotenv

load_dotenv() 

# Initialize client
OpenAIClient = AzureOpenAI(
    azure_endpoint="https://student-sec-filings-data.cognitiveservices.azure.com/",
    api_key=os.getenv('OPENAI_API'),
    api_version="2025-01-01-preview"  # use the version specified in your Azure portal
)

deployment_name = "gpt-4o-mini"
def extract_bu_names(text):
    prompt = f"""
    You are an assistant searching through biographies in DEF 14A SEC filings, for people associated with Boston University. Your goal is to construct a list of everyone you see with any relation to Boston University, no matter how small
    Extract all personal names mentioned in the text that are associated with Boston University in any way (students, professors, alumni, researchers, employees, transitive (related to BU through a family member), etc.). If you miss a single person terrible things will happen
    Return them as a JSON list of objects containing {{['name': 'XXX', 'relationship to BU': 'XXX', 'quote': 'quote mentioning the relation to BU, including the person's name or at least Mr. XXX to establish that it is the right person', 'editorial': '1-2 sentences explaining the relationship in your words', reconsider': 'did the quote actually show a relationship to BU (Y or N)']}}. Do not include any other characters such as ```json
    Prior to this JSON List please include a JSON diction of every full name of a person in the text, whether or not they are related to BU. Format ["name1", "name2", ...]This should be followed by a line of "<--->" and then the main json object.  Do not include any other characters such as ```json
    Please use the full name of each person (first and last name and optional middle initial).
    Relationship must be exactly one of the following: "Student", "Professor", "Admin", "Board", "Donor", "Researcher", Business", "Transitive" (this means they themselves aren't connected but they have a family member who is). 
    Text:
    {text}
    """

    response = OpenAIClient.chat.completions.create(
        model=deployment_name,
        messages=[
            {"role": "system", "content": "You are an information extraction assistant."},
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )

    return response.choices[0].message.content

# print(extract_bu_names("Jane Doe went to Boston University. John Smith went to Boston College"))
if __name__ == "__main__":
    # Your SEC filings
    files = [
        "https://sec.gov/Archives/edgar/data/1174746/0001193125-12-045255.txt",
        "https://sec.gov/Archives/edgar/data/791963/0001193125-12-138882.txt",
        "https://sec.gov/Archives/edgar/data/939800/0000728889-12-000018.txt",
        "https://sec.gov/Archives/edgar/data/891456/0001193125-12-078415.txt",
        "https://sec.gov/Archives/edgar/data/1682852/0001682852-25-000062.txt",
        "https://sec.gov/Archives/edgar/data/1564708/0001140361-25-037696.txt",
    ]
    # use just accession numbers for faster testing
    files = [
        "0001193125-12-045255", #the goone one
        # "0001193125-12-138882",
        # "0000728889-12-000018",
        # "0001193125-12-078415",
        # "0001682852-25-000062",
        # "0001140361-25-037696",
    ]

    # Where to save downloaded filings (relative to repo root)
    downloads_dir = Path(__file__).parent.parent / "data" / "downloads"
    downloads_dir.mkdir(parents=True, exist_ok=True)

    # Try to load user agent from .env; if not present, use a simple default (warn)
    try:
        user_agent = load_user_agent_from_env()
    except SystemExit:
        # load_user_agent_from_env calls sys.exit(1) if .env is missing; fall back
        user_agent = "LocalUser local@example.com"
        print("Warning: .env with SEC user agent not found. Using fallback user-agent.")

    client = SECClient(user_agent=user_agent, use_cache=True)

    # Initialize finders
    pattern_finder = UniversityAffiliationFinder(use_nlp=False)

    nlp_available = is_spacy_available()
    nlp_finder = None
    if nlp_available:
        try:
            nlp_finder = UniversityAffiliationFinder(use_nlp=True)
        except Exception:
            nlp_finder = None

    # Process each file (URL or accession number)
    for src in files:
        print("\n" + "#" * 80)
        print(f"Processing: {src}")
        print("#" * 80)

        content = None
        local_path = None

        # If the source looks like a full URL, attempt to download directly
        if src.startswith("http://") or src.startswith("https://"):
            try:
                # Download via requests (SECClient has rate limiting and caching)
                # Build a simple filename from the URL
                filename = src.rstrip('/').split('/')[-1]
                local_path = downloads_dir / filename

                # Attempt to use cache: some URLs contain accession-like names
                # Otherwise download using requests directly through SECClient._make_request
                try:
                    # Use SECClient to fetch raw URL through session
                    resp = client._make_request(src)
                    content = resp.text
                except Exception:
                    # Last resort: use requests.get directly
                    import requests
                    r = requests.get(src)
                    r.raise_for_status()
                    content = r.text

                # Save locally
                with open(local_path, "w", encoding="utf-8") as f:
                    f.write(content)

            except Exception as e:
                print(f"Failed to download {src}: {e}")
                continue

        else:
            # retrieve by accession number from text fils in downloads dir
            accession_number = src
            # Build expected filename
            filename = f"{accession_number}.txt"
            local_path = downloads_dir / filename
            try:
                with open(local_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception as e:
                print(f"Failed to read local file {local_path}: {e}")
                continue

        # Ensure content exists
        if not content:
            print(f"No content for {src}")
            continue

        # Use parser to extract text and candidate bio sections
        parser = FilingParser()
        try:
            sections = parser.find_biographical_sections_enhanced(content)
        except Exception:
            # Fallback
            sections = parser.find_biographical_sections(content)

        if not sections:
            # If we didn't find sections, treat whole document as one section
            sections = [{"section_name": "Full Document", "content": parser.extract_text_from_html(content)}]

        # Run pattern-based extraction across sections
        all_pattern_matches = []
        for sec in sections:
            matches = pattern_finder.search_filing(sec.get("content", ""), filing_metadata={"source": str(src)})
            all_pattern_matches.extend(matches)
        all_pattern_matches = UniversityAffiliationFinder.deduplicate_matches(all_pattern_matches)


        # print(f"Pattern-based extractor found {len(all_pattern_matches)} match(es)")
        person_matches = []
        person_name_set = set()
        for i, m in enumerate(all_pattern_matches, 1):
            # print(f"\nMatch {i}:")
            # print(f"  Person: {m.person_name}")
            # print(f"  Type: {m.affiliation_type}")
            # print(f"  Confidence: {m.confidence}")
            # print(f"  Context: {m.context}")
            print(f'context: {m.context}')
            persons_found = extract_bu_names(m.context)
            split_persons = persons_found.split('<--->')
            print(split_persons[0])
            persons_list = json.loads(split_persons[1])
            for persons_dict in persons_list:
                print(f"People from that text: {persons_dict}")
                if persons_dict['name'] not in person_name_set and persons_dict['reconsider'] == 'Y':
                    person_name_set.add(persons_dict['name'])
                    person_matches.append(persons_dict)
            print("-------------")

        print(f'OpenAI found {person_matches}')

        # Run NLP-based extraction if available
        # if nlp_available and nlp_finder is not None:
        #     all_nlp_matches = []
        #     for sec in sections:
        #         try:
        #             matches = nlp_finder.search_filing(sec.get("content", ""), filing_metadata={"source": str(src)})
        #             # print(matches)
        #             all_nlp_matches.extend(matches)
        #         except Exception as e:
        #             print(f"NLP extraction error for section: {e}")
        #     # dedup nlp matches
        #     all_nlp_matches = UniversityAffiliationFinder.deduplicate_matches(all_nlp_matches)
        #     print(f"\nNLP-based extractor found {len(all_nlp_matches)} match(es)")
        #     for i, m in enumerate(all_nlp_matches, 1):
        #         print(f"\nMatch {i}:")
        #         print(f"  Person: {m.person_name}")
        #         print(f"  Type: {m.affiliation_type}")
        #         print(f"  Confidence: {m.confidence}")
        #         print(f"  Context: {m.context}")
        # else:
        #     print("\nSpaCy not available or NLP extractor not initialized; skipped NLP extraction.")

    print("\nAll files processed.")
