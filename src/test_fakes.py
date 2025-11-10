"""
SEC Filings Parser - Run both NLP and pattern-based parsers on specific files
"""
import os
import csv
from pathlib import Path
from datetime import datetime
import re
from src.sec_filings import (
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
from src.sec_filings.database import postgres_connect, insert_alumni, insert_bu_name, alumni_match, insert_employment_history, insert_degree, insert_filing, \
    update_alumni, update_bu_name, update_employment_history, update_degree, update_filing, upsert_alumni, alumni_worked_at
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

def openai_wrapper(prompt, model):
    response = OpenAIClient.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a helpful assistant that extracts information from SEC filings."},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content

def anthropic_wrapper(prompt, model):
    response = anthropic_messages.create(
        model=model,
        max_tokens=1000,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    return response.content[0].text


deployment_name = "gpt-4o-mini"
def extract_bu_names(text, FILING_DATE, client=OpenAIClient):
    prompt = f"""
    You are an assistant searching through biographies in DEF 14A SEC filings, for people associated with Boston University. Your goal is to construct a list of everyone you see with any relation to Boston University, no matter how small
    Extract all personal names mentioned in the text that are associated with Boston University in any way (current students, alumni, professors, researchers, employees, transitive (related to BU through a family member), etc.). If you miss a single person terrible things will happen
    Return them as a JSON list of objects containing {{['name': 'XXX', 'quote': 'quote mentioning the relation to BU, including the person's name or at least Mr. XXX to establish that it is the right person', 'relationship to BU': 'XXX', 'year_of_birth': 'XXX', 'editorial': '1-2 sentences explaining the relationship in your words', 'reconsider': 'did the quote actually show a relationship to BU (Y or N)']}}. Do not include any other characters such as ```json
    Please use the full name of each person (first and last name(s) only, don't include middle initial). If you cannot find the name, write "Unknown". Year of birth should be a 4-digit year if available, otherwise null. You can calculate this from their current age if given. The filing date is {FILING_DATE}
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
    return openai_wrapper(prompt, deployment_name)



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
    return openai_wrapper(prompt, deployment_name)

def extract_employment_history(text, PERSON_NAME, COMPANY_NAME, client=OpenAIClient):
    prompt = f"""
    You are an assistant searching through biographies in DEF 14A SEC filings for employment history. Your goal is to find all companies that {PERSON_NAME} has worked at mentioned in the text.
    Extract all companies where {PERSON_NAME} has been employed, along with any available information about dates and compensation. If you miss a single company terrible things will happen
    Return them as a JSON list of objects containing {{['company_name': 'XXX', 'year_start': 'XXX', 'year_end': 'XXX', 'compensation': 'XXX', 'location': 'XXX']}}. Do not include any other characters such as ```json
    Please use the full official name of each company
    For year_start and year_end: Use the year as a 4-digit number (e.g., "2015"). If only one year is mentioned, put it in year_start and leave year_end as null. If the person currently works there, put "present" in year_end. If no dates are available, use null
    For compensation: Written text outlining any salary, bonus, stock options, or other compensation mentioned. If not available, use null. Location should be just the city name if available, otherwise null
    If a company is mentioned but no employment relationship is clear, do not include it. The company whose filing this is is called {COMPANY_NAME}; include this as well, and if "The Company" is used to refer to it, recognize that as well
    Text:
    {text}
    """
    return openai_wrapper(prompt, deployment_name)

def extract_degree(text, PERSON_NAME, client=OpenAIClient):
    prompt = f"""
    You are an assistant searching through biographies in DEF 14A SEC filings for educational degrees. Your goal is to find all degrees at Boston University that {PERSON_NAME} has obtained mentioned in the text.
    Extract all degrees at Boston University where {PERSON_NAME} has graduated, along with any available information about field of study and graduation year. If you miss a single degree terrible things will happen
    Return them as a JSON list of objects containing {{['school': 'School within BU, e.g. School of Law, do not include the words Boston University', 'degree_type': 'abbrevation, no period, e.g. MBA, JD, BS', 'end_year': 'XXX', 'start_year': 'XXX']}}.
    The list of acceptable BU Schools is as follows
    - School of Medicine
    - College of Arts & Sciences
    - College of Communication
    - College of Engineering
    - College of Fine Arts
    - Faculty of Computing & Data Sciences
    - Frederick S. Pardee School of Global Studies
    - Graduate Medical Sciences
    - Henry M. Goldman School of Dental Medicine
    - Metropolitan College
    - Questrom School of Business
    - Sargent College of Health & Rehabilitation Sciences
    - School of Hospitality Administration
    - School of Law
    - School of Public Health
    - School of Social Work
    - School of Theology
    - Wheelock College of Education & Human Development
    - Division of Military Education
    The list of acceptable degree types is as follows
    - BA, BS, BFA, BM, BBA
    - MA, MS, MArch, MBA, MSBA, MEd, MEng, MM, MPH
    - PhD, EdB, DBA, JD, MD, DScD, LLM
    - if a degree is mentioned but not equal or an offshoot of these, include it as written in the text
    For start and end years: Use the year as a 4-digit number (e.g., "2015"). If no year is available, use null
    Do not include any other characters such as ```json
    Text:
    {text}
    """
    return openai_wrapper(prompt, deployment_name)


def parse_company_index(file_path):
    file_list = []
    company_names = []
    company_ciks = []
    filing_dates = []
    with open(file_path, 'r') as f:
        lines = f.readlines()
        for line in lines[10:]:
            # split by multiple whitespaces
            parts = re.split(r'\s{2,}', line.strip())
            if parts[1] == 'DEF 14A':
                # sleep(0.1)
                url = f'https://www.sec.gov/Archives/{parts[4]}'
                company_names.append(parts[0])
                company_ciks.append(parts[2].zfill(10))
                filing_dates.append(parts[3])
                file_list.append(url)
    return file_list, company_names, company_ciks, filing_dates

def remove_jsonmarkdown(text):
    """
    If text is wrapped in ``json ```, remove those markers and only keep middle
    """
    pattern = r'```json(.*?)```'
    cleaned_text = re.sub(pattern, r'\1', text, flags=re.DOTALL)
    return cleaned_text.strip()


def process_person_matches(
    person_matches, company_name, company_cik, filing_date, file_link, conn,
    alum_function=None, name_function=None, degree_function=None, filing_function=None, employment_function=None):
    """
    Go from people's names to inserting all info into the database
    """
    for persons_dict in person_matches:
        matching_text = persons_dict['matching_text']
        # check if name is already in database
        existing_alumni = alumni_match(persons_dict['name'], conn)
        alum_function = upsert_alumni
        name_function = insert_bu_name
        degree_function = insert_degree
        filing_function = insert_filing
        if existing_alumni:
            # Use update functions
            print(f'{persons_dict["name"]} already exists in database with ID {existing_alumni}')
            name_function = update_bu_name
            degree_function = update_degree
            filing_function = update_filing
        # Alumni Table
        new_id = alum_function(persons_dict, conn)
       
        # Name Table
        name_function(new_id, persons_dict['name'], conn)
        print(f'Inserted {persons_dict["name"]} with ID {new_id} into database.')
    
        # Employment History
        employment_history = extract_employment_history(matching_text, persons_dict['name'], company_name)
        print(f'Employment history for {persons_dict["name"]}: {employment_history}')
        
        cleaned_employment_history = remove_jsonmarkdown(employment_history)
        employment_list = json.loads(cleaned_employment_history)

        for employment_dict in employment_list:
            if alumni_worked_at(new_id, employment_dict.get('company_name', None), conn):
                update_employment_history(new_id, employment_dict, conn)
            else:
                insert_employment_history(new_id, employment_dict, conn)
        # BU degrees
        bu_degrees = extract_degree(matching_text, persons_dict['name'])
        print(f'BU degrees found: {bu_degrees}')
        cleaned_bu_degrees = remove_jsonmarkdown(bu_degrees)
        degree_list = json.loads(cleaned_bu_degrees)
        for degree_dict in degree_list:
            degree_function(new_id, degree_dict, conn)
        # insert filing
        filing_function(new_id, str(file_link), company_name, company_cik, matching_text, filing_date, conn)
        # other universities
        # other_universities = extract_university_names(context)
        # print(f'Other universities found: {other_universities}')
    
        print("-------------")
    return None

import json

def reconcile_person_matches(all_pattern_matches, filing_date, extract_bu_names):
    """
    Extracts and reconciles unique person matches from pattern matches.
    
    Args:
        all_pattern_matches (list[str]): List of matching text segments.
        filing_date (str): Filing date for name extraction.
        extract_bu_names (callable): Function to extract names given text and filing date. (changeable so that it can be tested deterministically)
    
    Returns:
        list[dict]: List of reconciled person match dictionaries.
    """
    titles = ['Mr.', 'Ms.', 'Mrs.', 'Dr.']
    person_matches = []
    title_matches = []
    title_names_set = set()
    person_name_set = set()
    last_name_set = set()
    
    for matching_text in all_pattern_matches:
        persons_found = extract_bu_names(matching_text, filing_date)
        cleaned_persons_found = remove_jsonmarkdown(persons_found)
        persons_list = json.loads(cleaned_persons_found)
        
        for persons_dict in persons_list:
            persons_dict['matching_text'] = matching_text
            name = persons_dict['name']
            reconsider = persons_dict.get('reconsider') == 'Y'
            
            if not reconsider:
                continue
            # If the name has a title, add to title matches
            if any(title in name for title in titles):
                if name not in title_names_set:
                    title_names_set.add(name)
                    title_matches.append(persons_dict)
            # if the name has no title, add to person matches if its new
            else:
                if name not in person_name_set:
                    person_name_set.add(name)
                    last_name_set.add(name.split()[-1])
                    person_matches.append(persons_dict)
    
    # Include only titled names whose last name not already in last_name_set
    for title_dict in title_matches:
        last_name = title_dict['name'].split()[-1]
        if last_name not in last_name_set:
            person_matches.append(title_dict)
            last_name_set.add(last_name)
    
    return person_matches


if __name__ == "__main__":
    # download all DEF 14A filings from a certain quarter for testing
    files, company_names, company_ciks, filing_dates = parse_company_index('data/q2_2005.idx')
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
    conn = postgres_connect()

    # Process each file (URL or accession number)
    for file_index in range(len(files)):
        src = files[file_index]
        company_name = company_names[file_index]
        company_cik = company_ciks[file_index]
        filing_date = filing_dates[file_index]
        print("\n" + "#" * 80)
        print(f"Processing: | {company_name} | {company_cik} | {filing_date} | \n {src} number of files left: {len(files)-files.index(src)-1}")
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
        if len(content) > 100000000:
            print("Content too large, skipping")
            continue
        print("Made it to pre-parser")
        # Use parser to extract text and candidate bio sections
        parser = FilingParser()
        content = parser.extract_text_from_html(content)
        try:
            # sections = parser.find_biographical_sections_enhanced(content)
            sections = parser.find_bu_sections(content)
        except Exception:
            # Fallback
            sections = parser.find_bu_sections(content)

        # Run pattern-based extraction across sections
        all_pattern_matches = []
        for sec in sections:
            all_pattern_matches.append(sec['content'])

        print(f"Commencing the BU extraction with {len(all_pattern_matches)} candidate sections...")

        person_matches = reconcile_person_matches(all_pattern_matches, filing_date, extract_bu_names)
        print(f'After title reconciliation, found {len(person_matches)} unique person matches related to BU.')
        # calculate other info

        process_person_matches(person_matches, company_name, company_cik, filing_date, src, conn)

        # print(f'OpenAI found {person_matches}')

    print("\nAll files processed.")
    conn.close()