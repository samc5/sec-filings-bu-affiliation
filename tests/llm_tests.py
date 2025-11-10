import json
from src.test_fakes import reconcile_person_matches, parse_company_index, remove_jsonmarkdown, process_person_matches
from unittest.mock import patch, Mock
from tests.database_tests import schema_conn

def mock_extract_bu_names(text, filing_date):
    # Example mock output that the function would normally return as JSON
    if "case1" in text:
        return json.dumps([
            {"name": "John Smith", "reconsider": "Y"},
            {"name": "Alice Brown", "reconsider": "Y"},
            {"name": "Ms. Brown", "reconsider": "Y"}
        ])
    elif "case2" in text:
        return json.dumps([
            {"name": "Ms. Doe", "reconsider": "Y"},
            {"name": "John Smith", "reconsider": "N"}  # ignored
        ])
    return json.dumps([])

def test_reconcile_person_matches():
    all_pattern_matches = ["case1", "case2"]
    filing_date = "2025-11-10"
    
    result = reconcile_person_matches(all_pattern_matches, filing_date, mock_extract_bu_names)
    
    names = [p['name'] for p in result]
    
    # Expected: John Smith (from case1), Alice Brown (added because unique last name), Ms. Doe (from case2)
    assert "John Smith" in names
    assert "Alice Brown" in names
    assert "Ms. Brown" not in names  # Duplicate last name, should not be included
    assert "Ms. Doe" in names
    assert len(result) == 3

def test_remove_jsonmarkdown():
    text = """```json
    [{"name": "John Smith", "degree": "BSc"}, {"name": "Alice Brown", "degree": "MSc"}]
    ```"""
    cleaned = remove_jsonmarkdown(text)
    expected = '[{"name": "John Smith", "degree": "BSc"}, {"name": "Alice Brown", "degree": "MSc"}]'
    assert cleaned == expected

def test_parse_company_index():
    index_file = "tests/files/q1_2025.idx"
    file_list, company_names, company_ciks, filing_dates = parse_company_index(index_file)
    # print(company_names, company_ciks, filing_dates, file_list)
    assert company_names == ["&PARTNERS", "0xSecure Fund I, a series of WillowTech Ventures, LP", "1 800 FLOWERS COM INC"]
    assert company_ciks == ["0000107136", "0001996402", "0001084869"]
    assert filing_dates == ["2025-02-14", "2025-01-13", "2025-01-31"]
    assert file_list == ["https://www.sec.gov/Archives/edgar/data/107136/0001214659-25-002647.txt", "https://www.sec.gov/Archives/edgar/data/1996402/0001996402-25-000001.txt", "https://www.sec.gov/Archives/edgar/data/1084869/0001437749-25-002365.txt"]

def test_process_person_matches_flow(schema_conn):
    """
    Running through this with fake data and returns
    Ensuring that logic doesn't crash
    """
    conn = schema_conn
    person_matches = [
        {"name": "Alice Example", "matching_text": "worked at BU"},
        {"name": "Bob Example", "matching_text": "worked at Acme"}
    ]

    # Create mocks for the database functions
    mock_alum = Mock(return_value=1)
    mock_name = Mock()
    mock_degree = Mock()
    mock_filing = Mock()
    mock_employment = Mock()

    # Patch extract functions so they don’t call the LLM
    with patch('src.test_fakes.extract_employment_history', return_value='[{"company_name": "Acme"}]'), \
         patch('src.test_fakes.extract_degree', return_value='[{"degree": "BS"}]'), \
         patch('sec_filings.database.alumni_match', return_value=[]):

        process_person_matches(
            person_matches,
            company_name="Acme Corp",
            company_cik="0001234567",
            filing_date="2025-11-10",
            file_link="http://example.com/filing.txt",
            conn=conn,
            alum_function=mock_alum,
            name_function=mock_name,
            degree_function=mock_degree,
            filing_function=mock_filing,
            employment_function=mock_employment
        )