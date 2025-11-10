import pytest

import sys
from pathlib import Path
# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sec_filings.database import postgres_connect, search_buid, clean_relationship, clean_years, init_schema
import psycopg
from datetime import datetime

@pytest.fixture(scope="session")
def postgresql_proc(postgresql_proc):
    # pytest-postgresql's built-in fixture; starts a temporary Postgres instance
    return postgresql_proc

@pytest.fixture
def temp_db(postgresql):
    # 'postgresql' is a live psycopg.Connection, not a factory
    conn = postgresql
    dsn = conn.info.dsn  # connection DSN string
    db_params = {
        "dbname": conn.info.dbname,
        "user": conn.info.user,
        "password": "",  # pytest-postgresql doesn't set password
        "host": conn.info.host,
        "port": conn.info.port,
    }
    return db_params

@pytest.fixture
def monkeypatched_postgres_connect(monkeypatch, temp_db):
    def mock_connect():
        return psycopg.connect(**temp_db)
    monkeypatch.setattr("sec_filings.database.postgres_connect", mock_connect)
    return mock_connect

@pytest.fixture
def schema_conn(postgresql):
    conn = postgresql
    init_schema(conn, "tests/files/test_schema.sql")
    return conn

# tests/test_database_connection.py
def test_postgres_connect(monkeypatched_postgres_connect):
    conn = monkeypatched_postgres_connect()
    cur = conn.cursor()
    cur.execute("SELECT 1;")
    result = cur.fetchone()[0]
    assert result == 1
    cur.close()
    conn.close()


# postgres_connect - can DB connect

# init_schema - do all tables exist after it runs
# tests/test_database_connection.py
def test_init_schema(monkeypatched_postgres_connect):
    conn = monkeypatched_postgres_connect()
    init_schema(conn, "tests/files/test_schema.sql")
    cur = conn.cursor()
    cur.execute("SELECT table_name FROM information_schema.tables")
    results = [r[0] for r in cur.fetchall()]
    table_names = ["alumni", "foreign_alumni", "alumni_relationships", "name", "foreign_name", "degree", "companies", "filings", "foreign_filings", "employment_history"]
    for table in table_names:
        assert table in results



# alumni_match
# if unknwon it returns []
# otherwise it returns all alumni ids matching
# so 1 and 2 match versions

# tests/test_database_connection.py
def test_alumni_match(schema_conn):
    conn = schema_conn
    cur = conn.cursor()
    # Insert test data
    cur.execute("INSERT INTO alumni (id) VALUES (1), (2), (3);")
    cur.execute("INSERT INTO name (alumni_id, full_name) VALUES (1, 'John Smith'), (2, 'John Smith'), (3, 'Jane Doe');")
    conn.commit()
    cur.close()
    # Test matching
    from sec_filings.database import alumni_match
    result = alumni_match("John Smith", conn=conn)
    assert set([r[0] for r in result]) == {1, 2}
    result = alumni_match("Jane Doe", conn=conn)
    assert result[0][0] == 3
    result = alumni_match("Unknown", conn=conn)
    assert result == []

#search buid
# return None

# tests/test_database_connection.py
def test_search_buid():
    result = search_buid("john smith")
    assert result == None 


# Clean relationshio
# list of student, professor, admin, advisor, board_of_trustees, donor, researcher, business, transitive, alumni, alumnus, "unknwon" -> None
# tests/test_database_connection.py
def test_clean_relationship():
    test_list = ["student", "professor", "admin", "advisor", "board_of_trustees", "donor", "researcher", "business", "transitive", "alumni", "alumnus", "other", "unknown", None, "Student", "Alumnus", "Transitive", "Unknown"]
    res = []
    for item in test_list:
        res.append(clean_relationship(item))
    assert res == ["student", "professor", "admin", "advisor", "board_of_trustees", "donor", "researcher", "business", "transitive", "student", "student", None, None, None, "student", "student", "transitive", None]

# insert_alumni
# try it with a few alum_returns, some with Nones, make sure that database has a new row with that

def test_insert_alumni(schema_conn):
    conn = schema_conn
    cur = conn.cursor()
    from sec_filings.database import insert_alumni
    test_returns = [
        {"relationship to BU": "student", "year_of_birth": 2010, "full_name": "Bob Noyce"},
        {"relationship to BU": "alumnus", "year_of_birth": None, "full_name": "Chris Carino"},
        {"relationship to BU": None, "year_of_birth": 2005, "full_name": "Tim Capstraw"}
    ]
    for ret in test_returns:
        new_id = insert_alumni(ret, conn=conn)
        cur.execute("SELECT buid, relationship_to_bu, year_of_birth FROM alumni WHERE alumni.id = %s;", (new_id,))
        row = cur.fetchone()
        assert row[0] == search_buid(ret["full_name"])
        expected_relationship = clean_relationship(ret["relationship to BU"])
        assert row[1] == expected_relationship
        assert row[2] == ret["year_of_birth"]
        # assert row[3] == ret["full_name"]
    cur.close()


# update_alumni
# try with a few alum returns, some with Nones, some where the db is already filled in
# ensure that a yob difference of 2 years or less is considered fine, 

def test_update_alumni(schema_conn):
    conn = schema_conn
    cur = conn.cursor()
    from sec_filings.database import insert_alumni, update_alumni
    # Insert initial alumni
    initial_returns = [
        {"relationship to BU": None, "year_of_birth": 2010, "full_name": "Alice Johnson"},
        {"relationship to BU": "alumnus", "year_of_birth": 2000, "full_name": "David Lee"}
    ]
    alumni_ids = []
    for ret in initial_returns:
        new_id = insert_alumni(ret, conn=conn)
        alumni_ids.append(new_id)
    # Update alumni
    update_returns = [
        {"relationship to BU": "alumnus", "year_of_birth": 2011, "full_name": "Alice Johnson"},  # yob within 2 years
        {"relationship to BU": None, "year_of_birth": 1995, "full_name": "David Lee"}  # Should make a new person - a second david lee
    ]
    for alum_id, ret in zip(alumni_ids, update_returns):
        update_alumni(alum_id, ret, conn=conn)
    cur.execute("SELECT id, relationship_to_bu, year_of_birth FROM alumni ORDER BY id;")
    rows = cur.fetchall()
    # First alumni should be updated
    assert rows[0][1] == "student"  # relationship should be updated
    assert rows[0][2] == 2010 # yob should not update
    # Second alumni should remain unchanged
    assert rows[1][1] == "student"  # relationship should not change
    assert rows[1][2] == 2000
    # Third alumni should be new david lee
    assert rows[2][1] == None
    assert rows[2][2] == 1995
    cur.close()

# upsert
# one where it already exists and check that it is updated, one where it doesn't and check thatnew one it inserted

def test_upsert_alumni(schema_conn):
    conn = schema_conn
    cur = conn.cursor()
    from sec_filings.database import insert_alumni, upsert_alumni, insert_bu_name
    # Insert initial alumni and name
    initial_return = {"relationship to BU": "student", "year_of_birth": 2012, "name": "Evita Peron"}
    alum_id = insert_alumni(initial_return, conn=conn)
    insert_bu_name(alum_id, "Evita Peron", conn=conn)
    # Upsert with same info - shouldn't update
    upsert_return_1 = {"relationship to BU": "alumnus", "year_of_birth": 2013, "name": "Evita Peron"}
    first_alum_id = upsert_alumni(upsert_return_1, conn=conn)
    cur.execute("SELECT relationship_to_bu, year_of_birth FROM alumni WHERE id = %s;", (alum_id,))
    row = cur.fetchone()
    assert row[0] == "student"  # relationship should not change
    assert row[1] == 2012  # yob shouldb't update
    assert first_alum_id == alum_id
    # Upsert with new name - should insert new
    upsert_return_2 = {"relationship to BU": "student", "year_of_birth": 2012, "name": "Franklin D Roosevelt"}
    new_alum_id = upsert_alumni(upsert_return_2, conn=conn)
    assert new_alum_id != alum_id


#insert name
# one with BU and one with not BU
# must already have that alumni_id in the d, b

def test_insert_bu_name(schema_conn):
    conn = schema_conn
    cur = conn.cursor()
    from sec_filings.database import insert_alumni, insert_bu_name
    # Insert alumni
    alum_return = {"relationship to BU": "student", "year_of_birth": 2015, "full_name": "George Washington"}
    alum_id = insert_alumni(alum_return, conn=conn)
    # Insert BU name
    insert_bu_name(alum_id, "George Washington", conn=conn)
    # Verify name
    cur.execute("SELECT full_name FROM name WHERE alumni_id = %s;", (alum_id,))
    names = [r[0] for r in cur.fetchall()]
    assert "George Washington" in names
    cur.close()

# update_name
# one with BU and one with not BU

def test_update_bu_name(schema_conn):
    conn = schema_conn
    cur = conn.cursor()
    from sec_filings.database import insert_alumni, insert_bu_name, update_bu_name
    # Insert alumni
    alum_return = {"relationship to BU": "student", "year_of_birth": 2018, "full_name": "Ted Great"}
    alum_id = insert_alumni(alum_return, conn=conn)
    # Insert BU name
    insert_bu_name(alum_id, "Ted Great", conn=conn)
    # Update name
    update_bu_name(alum_id, "Theodore Great", conn=conn, force=False)
    # Verify name didn't update
    cur.execute("SELECT full_name FROM name WHERE alumni_id = %s;", (alum_id,))
    name = cur.fetchone()[0]
    assert name == "Ted Great"
    # Force update name
    update_bu_name(alum_id, "Theodore Great", conn=conn, force=True)
    # Verify name updated
    cur.execute("SELECT full_name FROM name WHERE alumni_id = %s;", (alum_id,))
    name = cur.fetchone()[0]
    assert name == "Theodore Great"
    cur.close()
# insert_degree
# few different degree returns

def test_insert_degree(schema_conn):
    conn = schema_conn
    cur = conn.cursor()
    from sec_filings.database import insert_alumni, insert_degree
    # Insert alumni
    alum_return = {"relationship to BU": "student", "year_of_birth": 2016, "name": "Helen Keller"}
    alum_id = insert_alumni(alum_return, conn=conn)
    # Insert degrees
    degree_returns = [
        {"degree_type": "BS", "school": "School of Law", "start_year": None, "end_year": 2020},
        {"degree_type": "MS", "school": "College of Engineering", "start_year": 2021, "end_year": None}
    ]
    for deg in degree_returns:
        insert_degree(alum_id, deg, conn=conn)
    # Verify degrees
    cur.execute("SELECT degree_type, school, start_year, end_year FROM degree WHERE alumni_id = %s;", (alum_id,))
    rows = cur.fetchall()
    assert len(rows) == 2
    assert ("BS", "School of Law", None, 2020) in rows
    assert ("MS", "College of Engineering", 2021, None) in rows
    cur.close()


# update_degree
# Four different degree returns, some with db already having info filled in
def test_update_degree(schema_conn):
    conn = schema_conn
    cur = conn.cursor()
    from sec_filings.database import insert_alumni, insert_degree, update_degree
    # Insert alumni
    alum_return = {"relationship to BU": "student", "year_of_birth": 2017, "name": "Isaac Newton"}
    alum_id = insert_alumni(alum_return, conn=conn)
    # Insert initial degrees
    initial_degrees = [
        {"degree_type": None, "school": "College of Fine Arts", "start_year": 2015, "end_year": 2019},
        {"degree_type": "MS", "school": "Faculty of Computing and Data Sciences", "start_year": None, "end_year": 2023},
        {"degree_type": "PhD", "school":None, "start_year": 2018, "end_year": None}
    ]
    deg_ids = []
    for deg in initial_degrees:
        new_id = insert_degree(alum_id, deg, conn=conn)
        deg_ids.append(new_id)
    # Update degrees
    update_degrees = [
        {"degree_type": "BA", "school": "College of Fine Arts", "start_year": 2015, "end_year": 2019},  # school should update,
        {"degree_type": "MS", "school": "Graduate Medical School", "start_year": None, "end_year": 2023}, # shouldn't update anything
        {"degree_type": "PhD", "school": "Frederick S. Pardee School of Global Studies", "start_year": 2020, "end_year": None}  # start_year should update
    ]
    for degree_dict in update_degrees:
        update_degree(alum_id, degree_dict, conn=conn)
    # Verify updates
    cur.execute("SELECT degree_type, school, start_year, end_year FROM degree WHERE alumni_id = %s ORDER BY degree_type;", (alum_id,))
    rows = cur.fetchall()
    assert rows[0] == ("BA", "College of Fine Arts", 2015, 2019)
    assert rows[1] == ("MS", "Faculty of Computing and Data Sciences", None, 2023)
    assert rows[2] == ("PhD", "Frederick S. Pardee School of Global Studies", 2018, None) 
    cur.close()

# find_company_by_name
# straightforward

def test_find_company_by_name(schema_conn):
    conn = schema_conn
    cur = conn.cursor()
    from sec_filings.database import insert_or_get_company, find_company_by_name
    # Insert companies
    company_names = ["Tech Corp", "Business Inc", "Enterprise LLC"]
    for name in company_names:
        insert_or_get_company({'company_name': name}, conn=conn)
    # Find companies
    for name in company_names:
        company_id = find_company_by_name(name, conn=conn)
        assert company_id is not None
    # Test non-existing company
    non_existing = find_company_by_name("NonExistent Co", conn=conn)
    assert not non_existing # empty list
    cur.close()

# find company_by_fuzzy_name
# figure out what exactly this does and put that in
def test_find_company_by_fuzzy_name(schema_conn):
    conn = schema_conn
    cur = conn.cursor()
    from sec_filings.database import insert_or_get_company, find_company_by_fuzzy_name
    # Insert companies
    company_names = ["Alpha Technologies", "Beta Solutions", "Gamma Enterprises"]
    for name in company_names:
        insert_or_get_company({'company_name': name}, conn=conn)
    # Fuzzy search companies
    fuzzy_names = ["Alpha Tech", "Beta Sol", "Gamma Ent"]
    for fuzzy in fuzzy_names:
        results = find_company_by_fuzzy_name(fuzzy, conn=conn)
        print(f"Fuzzy search for '{fuzzy}' returned: {results}")
        assert len(results) > 0
    # Test non-existing fuzzy name
    non_existing = find_company_by_fuzzy_name("Delta Corp", conn=conn)
    assert non_existing == []  # empty list
    cur.close()


# find_company_by_cik
# straightforward, have a few companies with ciks

def test_find_company_by_cik(schema_conn):
    conn = schema_conn
    cur = conn.cursor()
    from sec_filings.database import insert_or_get_company, find_company_by_cik
    # Insert companies with CIKs
    companies = [("Innovatech", "0001234567"), ("Global Solutions", "0002345678"), ("NextGen Corp", "0003456789")]
    for name, cik in companies:
        new_id = insert_or_get_company({'company_name': name, 'company_cik': cik}, conn=conn)
        print(f"Inserted company '{name}' with CIK '{cik}' and ID {new_id}")
    # Find companies by CIK
    for name, cik in companies:
        company_id = find_company_by_cik(cik, conn=conn)
        print(company_id)
        assert company_id is not None
    # Test non-existing CIK
    non_existing = find_company_by_cik("0009999999", conn=conn)
    assert not non_existing  # None
    cur.close()

# insert_or_get_company
# if company exists, return its id and verify nothing has changed, if not verify that it inserts and returns id

def test_insert_or_get_company(schema_conn):
    conn = schema_conn
    cur = conn.cursor()
    from sec_filings.database import insert_or_get_company
    # Actually fill the DB
    companies = [("innovatech", "0001234567"), ("global solutions", "0002345678")]
    insert_query = """
    INSERT INTO Companies (name, cik)
    VALUES (%s, %s)
    RETURNING id
    """
    for company_name, company_cik in companies:
        cur.execute(insert_query, (company_name, company_cik))
    # try function on several companies
    new_companies = [("Innovatech", "0001234567"), ("Innovatech 2", "1111111111"), ("Innovatech 2", "1121111111"), ("Innovatech 3", "111")]
    expected_results = [(1, "innovatech", "0001234567"), (3, "innovatech 2", "1111111111"), (3, "innovatech 2", "1111111111"), (4, "innovatech 3", None)]
    for (name, cik), (expected_id, expected_name, expected_cik) in zip(new_companies, expected_results):
        company_dict = {'company_name': name, 'company_cik': cik}
        company_id = insert_or_get_company(company_dict, conn=conn)
        cur.execute("SELECT id, name, cik FROM Companies WHERE id = %s;", (company_id,))
        row = cur.fetchone()
        assert row[0] == expected_id
        assert row[1] == expected_name.lower()
        assert row[2] == expected_cik
    count_query = "SELECT COUNT(*) FROM Companies;"
    cur.execute(count_query)
    total_companies = cur.fetchone()[0]
    assert total_companies == 4 
    
    cur.close()

# populate_companies
# run it on a smaller company list with same format, check that companies matches
def test_populate_companies(schema_conn):
    conn = schema_conn
    cur = conn.cursor()
    from sec_filings.database import populate_companies, find_company_by_name
    # Define a small list of companies
    test_tickers = [
        {"cik": "0001111111", "name": "Test Company A"},
        {"cik": "0002222222", "name": "Test Company B"},
        {"cik": "0003333333", "name": "Test Company C"}
    ]
    # Populate companies
    populate_companies(test_tickers, conn=conn)
    # Verify companies inserted
    for ticker in test_tickers:
        name_results = find_company_by_name(ticker["name"], conn=conn)
        company_id = name_results[0][0] if name_results else None
        assert company_id is not None
        find_query = "SELECT cik, name FROM Companies WHERE id = %s;"
        cur.execute(find_query, (company_id,))
        row = cur.fetchone()
        cik, name = row
        assert name == ticker["name"].lower()
        assert cik == ticker["cik"]


    cur.close()


# clean_years
# (present, present), (present, null), (null present), (null, null), (2010, present), (2008, 2020), (None, None), (2010, None), (None, 2018)
# tests/test_database_connection.py
def test_clean_years():
    year = datetime.now().year
    test_list = [("present", "present"), ("present", "null"), ("null", "present"), ("null", "null"), (2010, "present"), (2008, 2020), (None, None), (2010, None), (None, 2018), ("2010", "2017")]
    res = []
    for item in test_list:
        res.append(clean_years(item[0], item[1]))
    correct_results = [(None, 2025), (None, None), (None, 2025), (None, None), (2010, 2025), (2008, 2020), (None, None), (2010, None), (None, 2018), (2010, 2017)]
    assert res == correct_results

# alumni_worked at
# checks a few fake entries
def test_alumni_worked_at(schema_conn):
    conn = schema_conn
    cur = conn.cursor()
    from sec_filings.database import insert_alumni, insert_or_get_company, insert_employment_history, alumni_worked_at
    # Insert alumni
    alum_return = {"relationship to BU": "student", "year_of_birth": 2014, "name": "Mark Twain"}
    alum_id = insert_alumni(alum_return, conn=conn)
    # Insert companies
    company_names = ["Old Company", "New Company"]
    company_ids = {}
    for name in company_names:
        company_id = insert_or_get_company({'company_name': name}, conn=conn)
        company_ids[name] = company_id
    # Insert employment history
    employment_returns = [
        {"company_name": "Old Company", "year_start": 2015, "year_end": 2016},
        {"company_name": "New Company", "year_start": 2017, "year_end": None}
    ]
    for emp in employment_returns:
        insert_employment_history(alum_id, emp, conn=conn)
    # Check if alumni worked at companies
    assert alumni_worked_at(alum_id, "Old Company", conn=conn) == True
    assert alumni_worked_at(alum_id, "New Company", conn=conn) == True
    assert alumni_worked_at(alum_id, "NonExistent Co", conn=conn) == False
    cur.close()

# insert_employment_history
# if company_name is None empty it
# try with uppercase and lowercase names, get company_id if its in the db and make a new one if its not
def test_insert_employment_history(schema_conn):
    conn = schema_conn
    cur = conn.cursor()
    from sec_filings.database import insert_alumni, insert_employment_history, find_company_by_name, insert_or_get_company
    # Insert alumni
    alum_return = {"relationship to BU": "student", "year_of_birth": 2013, "name": "Sarah Connor"}
    alum_id = insert_alumni(alum_return, conn=conn)
    # Insert a company
    insert_or_get_company({'company_name': 'Fake Company'}, conn=conn)
    # Insert employment histories
    employment_returns = [
        {"company_name": "Future Tech", "year_start": 2020, "year_end": None}, # should be added with company id 2
        {"company_name": "future tech", "year_start": 2018, "year_end": 2019}, # shouldn't be input since it's a duplicate
        {"company_name": None, "year_start": 2015, "year_end": 2017}, # should not be added
        {"company_name": "Fake Company", "year_start": 2016, "year_end": 2018} # should be added with company id 1
    ]
    expected_returns = [
        (2, "future tech", 2020, None),
        (2, "future tech", 2020, None),
        [],
        (1, "fake company", 2016, 2018)
    ]
    for emp in employment_returns:
        insert_employment_history(alum_id, emp, conn=conn)
    # Verify employment histories
    for emp, expected in zip(employment_returns, expected_returns):
        company_name = emp["company_name"]
        if company_name is None:
            cur.execute("SELECT company_id, company_name, year_start, year_end FROM Employment_History WHERE alumni_id = %s AND company_name IS NULL;", (alum_id,))
        else:
            cur.execute("SELECT company_id, company_name, year_start, year_end FROM Employment_History WHERE alumni_id = %s AND company_name = %s;", (alum_id, emp["company_name"].lower()))
        row = cur.fetchall()
        if expected == []:
            assert row == []
        else:
            row = row[0]
            expected_id, expected_name, expected_start, expected_end = expected
            assert row[0] == expected_id
            assert row[1] == expected_name.lower()
            assert row[2] == expected_start
            assert row[3] == expected_end
    cur.close()

    

# update_employment_history
# if company name is not, return None, same test of a few inputs
# One 
def test_update_employment_history(schema_conn):
    conn = schema_conn
    cur = conn.cursor()
    from sec_filings.database import insert_alumni, insert_employment_history, update_employment_history
    # Insert alumni
    alum_return = {"relationship to BU": "student", "year_of_birth": 2012, "name": "Laura Palmer"}
    alum_id = insert_alumni(alum_return, conn=conn)
    # Insert employment histories
    employment_returns = [
        {"company_name": "Mystery Inc", "year_start": 2010, "year_end": 2012, "compensation": "$50000", "location": "New York"},
        {"company_name": "Enigma LLC", "year_start": None, "year_end": None, "compensation": None, "location": "Los Angeles"}
    ]
    for emp in employment_returns:
        insert_employment_history(alum_id, emp, conn=conn)
    # Update employment histories
    update_returns = [
        {"company_name": "Mystery Inc", "year_start": 2011, "year_end": 2013, "compensation": "$60000", "location": "Boston"},  # should update all fields
        {"company_name": "Enigma LLC", "year_start": 2015, "year_end": None, "compensation": "$70000", "location": "New York"},  # should update year_start and compensation
        {"company_name": None, "year_start": 2000, "year_end": 2005, "compensation": "$40000", "location": "Chicago"}  # should do nothing
    ]
    for emp in update_returns:
        update_employment_history(alum_id, emp, conn=conn)
    # Verify updates
    cur.execute("SELECT company_name, year_start, year_end, compensation, location FROM Employment_History WHERE alumni_id = %s ORDER BY company_name;", (alum_id,))
    rows = cur.fetchall()
    assert rows[0] == ("enigma llc", 2015, None, "$70000", "Los Angeles")
    assert rows[1] == ("mystery inc", 2010, 2012, "$50000", "New York")
    assert len(rows) == 2
    cur.close()


# insert filing
# insert properly a few documents, company stuff will already be teted
def test_insert_filing(schema_conn):
    conn = schema_conn
    cur = conn.cursor()
    from sec_filings.database import insert_or_get_company, insert_filing, insert_alumni
    # Insert alumni
    alum_returns = [
        {"relationship to BU": "student", "year_of_birth": 1990, "name": "Filing Alum 1"},
        {"relationship to BU": "alumnus", "year_of_birth": 1985, "name": "Filing Alum 2"},
        {"relationship to BU": "student", "year_of_birth": 1995, "name": "Filing Alum 3"}
    ]
    for ret in alum_returns:
        insert_alumni(ret, conn=conn)

    # Insert companies
    insert_or_get_company({'company_name': 'company1', 'company_cik': '0001111111'}, conn=conn)
    insert_or_get_company({'company_name': 'company2', 'company_cik': '0002222222'}, conn=conn)
    # Insert filings
    filing_returns = [
        {"alumni_id": 1, "file_link": "http://filing1.com", "company_name": "Company1", "company_cik": "0001111111", "text_extracted": "Filing text 1", "filing_date": "2023-01-01"},
        {"alumni_id": 2, "file_link": "http://filing2.com", "company_name": "Company2", "company_cik": "0002222222", "text_extracted": "Filing text 2", "filing_date": "2023-02-01"},
        {"alumni_id": 3, "file_link": "http://filing3.com", "company_name": "Company3", "company_cik": None, "text_extracted": "Filing text 3", "filing_date": "2023-03-01"}
    ]
    # test on company_id, alum_id, file_link, text_extracted, filing_date
    expected_return = [(1, 1, "http://filing1.com", "Filing text 1", "2023-01-01"),
                          (2, 2, "http://filing2.com", "Filing text 2", "2023-02-01"),
                          (3, 3, "http://filing3.com", "Filing text 3", "2023-03-01")]

    for filing in filing_returns:
        insert_filing(filing['alumni_id'], filing['file_link'], filing['company_name'], filing['company_cik'], filing['text_extracted'], filing['filing_date'], conn=conn)
    # Verify filings
    for ret, expected in zip(filing_returns, expected_return):
        alum_id, company_id, file_link, text_extracted, filing_date = expected
        cur.execute("SELECT alumni_id, company_id, link, text_extracted, date FROM filings WHERE alumni_id = %s AND link = %s;", (ret["alumni_id"], ret["file_link"]))
        row = cur.fetchone()
        assert row[0] == alum_id
        assert row[1] == company_id
        assert row[2] == file_link
        assert row[3] == text_extracted
        assert str(row[4]) == filing_date
# update filing
def test_update_filing(schema_conn):
    conn = schema_conn
    cur = conn.cursor()
    from sec_filings.database import insert_or_get_company, insert_filing, update_filing, insert_alumni
    # Insert alumni
    alum_return = {"relationship to BU": "student", "year_of_birth": 1992, "name": "Update Filing Alum"}
    alum_id = insert_alumni(alum_return, conn=conn)
    # Insert company
    insert_or_get_company({'company_name': 'UpdateCo', 'company_cik': '0003333333'}, conn=conn)
    # Insert filing
    insert_filing(alum_id, "http://updatefiling.com", "UpdateCo", "0003333333", "Initial filing text", None, conn=conn)
    # Update filing
    update_filing(alum_id, "http://updatefiling.com", "UpdateCo", "0003333333", "Updated filing text", "2023-04-01", conn=conn)
    # Verify update
    cur.execute("SELECT text_extracted, date FROM filings WHERE alumni_id = %s AND link = %s;", (alum_id, "http://updatefiling.com"))
    row = cur.fetchone()
    assert row[0] == "Initial filing text\nUpdated filing text"
    assert str(row[1]) == "2023-04-01"
    cur.close()
