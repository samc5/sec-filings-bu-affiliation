"""
SEC Filings Parser - Run both NLP and pattern-based parsers on specific files
"""
import os
import csv
from pathlib import Path
from datetime import datetime
import re
from sec_filings import (
    SECClient,
    UniversityAffiliationFinder,
    BiographyExtractor,
    FilingParser,
    load_user_agent_from_env,
    is_spacy_available
)
from openai import AzureOpenAI, OpenAI
import anthropic
import json
from dotenv import load_dotenv
from database import insert_alumni, insert_name, alumni_match, insert_employment_history, insert_degree, insert_filing
load_dotenv() 

# Initialize client
OpenAIClient = AzureOpenAI(
    azure_endpoint="https://student-sec-filings-data.cognitiveservices.azure.com/",
    api_key=os.getenv('OPENAI_API'),
    api_version="2025-01-01-preview"  # use the version specified in your Azure portal
)

GPT5Client = OpenAI(
    api_key=os.getenv('GARDOS_OPENAI_API')
    )

AnthropicClient = anthropic.Anthropic(
    api_key=os.getenv('ANTHROPIC_API_KEY')
)

gpt5_messages = GPT5Client.responses
anthropic_messages = AnthropicClient.messages
openai_messages = OpenAIClient.responses


# anthropic_response = anthropic_messages.create(
#     model="claude-sonnet-4-5",
#     max_tokens=1000,
#     messages=[
#         {"role": "user", "content": "say hi and give yourself a name"}
#     ]
# )
# print(anthropic_response.content[0].text)


deployment_name = "gpt-4o-mini"
def extract_bu_names(text, client=GPT5Client):
    prompt = f"""
    You are an assistant searching through biographies in DEF 14A SEC filings, for people associated with Boston University. Your goal is to construct a list of everyone you see with any relation to Boston University, no matter how small
    Extract all personal names mentioned in the text that are associated with Boston University in any way (current students, alumni, professors, researchers, employees, transitive (related to BU through a family member), etc.). If you miss a single person terrible things will happen
    Return them as a JSON list of objects containing {{['name': 'XXX', 'quote': 'quote mentioning the relation to BU, including the person's name or at least Mr. XXX to establish that it is the right person', 'relationship to BU': 'XXX', 'year_of_birth': 'XXX', 'editorial': '1-2 sentences explaining the relationship in your words', 'reconsider': 'did the quote actually show a relationship to BU (Y or N)']}}. Do not include any other characters such as ```json
    Please use the full name of each person (first and last name(s) only, don't include middle initial). If you cannot find the name, write "Unknown". Year of birth should be a 4-digit year if available, otherwise null
    Relationship must be exactly one of the following: "Student", "Professor", "Admin", "Board", "Donor", "Researcher", "Business", "Transitive". If you label it anything else, terrible things will happen
    - Student: Either currently enrolled or graduated from BU, with any degree. If they qualify for other categories (e.g., professor), still label as Student. This category includes all alumni.
    - Professor: Any teaching role at BU (professor, lecturer, instructor, adjunct). If they were a professor for another university but not BU, do not include them
    - Admin: Any administrative role at BU (dean, department head, etc.)
    - Board: Any role on the board of trustees or similar governing body at BU. This does not include advisory boards unless they are specifically governing BU 
    - Donor: Any significant financial contributor to BU
    - Researcher: Any role involved in research at BU (faculty, staff, student)
    - Business: Any role in a business relationship with BU (vendor, partner, advisor, consultant, etc.)
    - Transitive: Any indirect connection to BU (family member, etc.) (this means they themselves aren't connected but they have a family member who is).
    Text:
    {text}
    """

    response = client.chat.completions.create(
        model="gpt-5",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that extracts information from SEC filings."},
            {"role": "user", "content": prompt}
        ]
    )

    return response.choices[0].message.content



def extract_university_names(text, client=OpenAIClient):
    prompt = f"""
    You are an assistant searching through biographies in DEF 14A SEC filings, for people associated with universities. Your goal is to construct a list of everyone you see with any relation to any university, no matter how small
    Extract all personal names mentioned in the text that are associated with a university in any way (students, professors, alumni, researchers, employees, board members, donors, etc.). If you miss a single person terrible things will happen
    Return them as a JSON list of objects containing {{['name': 'XXX', 'university': 'XXX']}}. Do not include any other characters such as ```json
    Please use the full name of each person (first and last name(s) only, don't include middle initial). If you cannot find the name, write "Unknown"
    Please use the full official name of each university (e.g., "Boston University" not "BU"). Do not include the individual college within the university (e.g. Columbia University Graduate School of Business should be Columbia University)
    Text:
    {text}
    """
    response = client.chat.completions.create(
        model=deployment_name,
        messages=[
            {"role": "system", "content": "You are a helpful assistant that extracts information from SEC filings."},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content

def extract_employment_history(text, PERSON_NAME, client=OpenAIClient):
    prompt = f"""
    You are an assistant searching through biographies in DEF 14A SEC filings for employment history. Your goal is to find all companies that {PERSON_NAME} has worked at mentioned in the text.
    Extract all companies where {PERSON_NAME} has been employed, along with any available information about dates and compensation. If you miss a single company terrible things will happen
    Return them as a JSON list of objects containing {{['company_name': 'XXX', 'year_start': 'XXX', 'year_end': 'XXX', 'compensation': 'XXX', 'location': 'XXX']}}. Do not include any other characters such as ```json
    Please use the full official name of each company
    For year_start and year_end: Use the year as a 4-digit number (e.g., "2015"). If only one year is mentioned, put it in year_start and leave year_end as null. If the person currently works there, put "present" in year_end. If no dates are available, use null
    For compensation: Include any salary, bonus, stock options, or other compensation mentioned. If not available, use null. Location should be just the city name if available, otherwise null
    If a company is mentioned but no employment relationship is clear, do not include it
    Text:
    {text}
    """
    response = client.chat.completions.create(
        model=deployment_name,
        messages=[
            {"role": "system", "content": "You are a helpful assistant that extracts information from SEC filings."},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content

def extract_degree(text, PERSON_NAME, client=OpenAIClient):
    prompt = f"""
    You are an assistant searching through biographies in DEF 14A SEC filings for educational degrees. Your goal is to find all degrees at Boston University that {PERSON_NAME} has obtained mentioned in the text.
    Extract all degrees at Boston University where {PERSON_NAME} has graduated, along with any available information about field of study and graduation year. If you miss a single degree terrible things will happen
    Return them as a JSON list of objects containing {{['school': 'School within BU, e.g. School of Law, do not include the words Boston University', 'degree_type': 'abbrevation, no period, e.g. MBA, JD, BS', 'end_year': 'XXX', 'start_year': 'XXX']}}. Do not include any other characters such as ```json
    For start and end years: Use the year as a 4-digit number (e.g., "2015"). If no year is available, use null
    If a degree is mentioned but no graduation relationship is clear, do not include it
    Text:
    {text}
    """
    response = client.chat.completions.create(
        model=deployment_name,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content


def parse_company_index(file_path):
    # read the file and print 5 lines
    # download the file first
    file_list = []
    with open(file_path, 'r') as f:
        lines = f.readlines()
        for line in lines[11:]:
            # split by multiple whitespaces
            parts = re.split(r'\s{2,}', line.strip())
            if parts[1] == 'DEF 14A':
                # sleep(0.1)
                url = f'https://www.sec.gov/Archives/{parts[4]}'
                file_list.append(url)
    return file_list
    



# print(extract_bu_names("Jane Doe went to Boston University. John Smith went to Boston College"))
if __name__ == "__main__":
    # Your SEC filings
    files = [
        "https://sec.gov/Archives/edgar/data/1581068/0001104659-24-034494.txt", # Brixmor
        "https://sec.gov/Archives/edgar/data/889331/0001140361-24-013241.txt", # little fuse
        "https://sec.gov/Archives/edgar/data/742278/0001558370-24-003185.txt", # RES
        "https://sec.gov/Archives/edgar/data/800240/0001193125-24-067877.txt", # ODP corp
        "https://sec.gov/Archives/edgar/data/1371489/0001140361-24-013240.txt", # III
        "https://sec.gov/Archives/edgar/data/1558569/0001558370-24-003129.txt", # ISPC        "https://sec.gov/Archives/edgar/data/1052752/0001140361-24-013007.txt" # GTY
    ]
    # download all DEF 14A filings from a certain quarter for testing
    files = parse_company_index('../data/q1_2025.idx')
    print(f'Found {len(files)} DEF 14A filings in index')

    # Where to save downloaded filings (relative to repo root)
    downloads_dir = Path(__file__).parent.parent / "data" / "bulk" / "downloads"
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
        print(f"Processing: {src}, number of files left: {len(files)-files.index(src)-1}")
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

                # # Save locally
                # with open(local_path, "w", encoding="utf-8") as f:
                #     f.write(content)

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
        # print size of content
        print(f"Content size: {len(content)} characters")
        if len(content) > 10000000:
            print("Content too large, skipping")
            continue
        print("Made it to pre-parser")
        # Use parser to extract text and candidate bio sections
        parser = FilingParser()
        try:
            sections = parser.find_biographical_sections_enhanced(content)
        except Exception:
            # Fallback
            sections = parser.find_biographical_sections(content)
        if not sections:
            # If we didn't find sections, treat whole document as one section
            extracted_text = parser.extract_text_from_html(content)
            subbed = re.sub('\s{2,}', ' ', extracted_text)
            # replace more than 1 newline with 1
            subbed = re.sub('\n{2,}', '\n', subbed)
            sections = [{"section_name": "Full Document", "content": subbed}]

        # Run pattern-based extraction across sections
        all_pattern_matches = []
        for sec in sections:
            matches = pattern_finder.search_filing(sec.get("content", ""), filing_metadata={"source": str(src)})
            all_pattern_matches.extend(matches)
        # save to a json before dedup
        # json_path = downloads_dir / f"test_pattern_matches.json"
        # with open(json_path, "w", encoding="utf-8") as f:
        #     json.dump([m.__dict__ for m in all_pattern_matches], f, ensure_ascii=False, indent=2)

        # all_pattern_matches = UniversityAffiliationFinder.deduplicate_matches(all_pattern_matches)

        # # save sections to a json file
        # if src == files[0]:
        #     json_path = downloads_dir / f"test_sections.json"
        #     with open(json_path, "w", encoding="utf-8") as f:
        #         json.dump(sections, f, ensure_ascii=False, indent=2)

        print("Commencing the BU extraction")

        titles = ['Mr.', 'Ms.', 'Mrs.', 'Dr.']
        person_matches = []
        title_matches = []
        title_names_set = set()
        person_name_set = set()
        last_name_set = set()
        for i, m in enumerate(all_pattern_matches, 1):
            persons_found = extract_bu_names(m.context)
            persons_list = json.loads(persons_found)
            for persons_dict in persons_list:                
                if any(title in persons_dict['name'] for title in titles):
                    if persons_dict['name'] not in title_names_set and persons_dict['reconsider'] == 'Y':
                        title_names_set.add(persons_dict['name'])
                        title_matches.append(persons_dict)
                else:
                    if persons_dict['name'] not in person_name_set and persons_dict['reconsider'] == 'Y':
                        person_name_set.add(persons_dict['name'])
                        last_name_set.add(persons_dict['name'].split()[-1])
                        person_matches.append(persons_dict)
        # add titles in which don't appear in last name set
        for title_dict in title_matches:
            last_name = title_dict['name'].split()[-1]
            if last_name not in last_name_set:
                person_matches.append(title_dict)
                last_name_set.add(last_name)
        for persons_dict in person_matches:
            existing_alumni = alumni_match(persons_dict['name'])
            if existing_alumni:
                print(f'{persons_dict["name"]} already exists in database with ID {existing_alumni}')
            else:
                new_id = insert_alumni(persons_dict)
                insert_name('BU', new_id, persons_dict['name'])
                print(f'Inserted {persons_dict["name"]} with ID {new_id} into database.')
                # print employment history
                employment_history = extract_employment_history(m.context, persons_dict['name'])
                print(f'Employment history for {persons_dict["name"]}: {employment_history}')
                employment_list = json.loads(employment_history)
                for employment_dict in employment_list:
                    insert_employment_history(new_id, employment_dict)
                # BU degrees
                bu_degrees = extract_degree(m.context, persons_dict['name'])
                print(f'BU degrees found: {bu_degrees}')
                degree_list = json.loads(bu_degrees)
                for degree_dict in degree_list:
                    insert_degree(new_id, degree_dict)
                # insert filing
                insert_filing(new_id, str(src))

                    
                # other universities
                other_universities = extract_university_names(m.context)
                print(f'Other universities found: {other_universities}')

            print("-------------")

        print(f'OpenAI found {person_matches}')

    print("\nAll files processed.")
