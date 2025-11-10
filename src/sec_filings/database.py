import psycopg
import os
import dotenv
from src.sec_filings import SECClient, load_user_agent_from_env
from datetime import datetime
dotenv.load_dotenv()

def postgres_connect():
    conn = psycopg.connect(
        dbname=os.getenv('POSTGRES_DB'),
        user=os.getenv('POSTGRES_USER'),
        password=os.getenv('POSTGRES_PASSWORD'),
        host='localhost',
        port='5432'
    )
    return conn
standard_conn = postgres_connect()

def init_schema(conn=None, schema_file="../schema.sql"):
    close_after = False
    if conn is None:
        conn = postgres_connect()
        close_after = True
    with conn.cursor() as cur:
        with open(schema_file, "r") as f:
            cur.execute(f.read())
    conn.commit()
    if close_after:
        conn.close()


def alumni_match(full_name, conn):
    """
    Returns the alumni ID(s) matching the given full name
    """
    if full_name == "Unknown":
        return []
    # conn = postgres_connect()
    cursor = conn.cursor()
    query = """
    SELECT id
    FROM alumni LEFT JOIN Name
    ON (alumni.id = Name.alumni_id)
    WHERE Name.full_name = %s
    """
    cursor.execute(query, (full_name,))
    results = cursor.fetchall()
    cursor.close()
    return results

def search_buid(alumni_name):
    # Placeholder which will eventually search a BU database
    return None


def clean_relationship(relationship):
    """
    Fixes relationship mistakes made by 4o
    """
    accepted = ["student", "professor", "admin", "advisor","board_of_trustees", "donor", "researcher", "business", "transitive"]
    if relationship:
        relationship = relationship.lower()
    if relationship in accepted:
        return relationship
    if relationship == 'alumni' or relationship == 'alumnus':
        return 'student'

def insert_alumni(alum_return, conn):
    name = alum_return.get('name', None)
    yob = alum_return.get('year_of_birth', None)
    relationship = alum_return.get('relationship to BU', None)
    buid = search_buid(name)
    # conn = postgres_connect()
    cursor = conn.cursor()
    # Fix the relationship in predictable ways (e.g. alumni -> student)
    relationship = clean_relationship(relationship)
    # insert into alumni table, create new id
    insert_query = """
    INSERT INTO Alumni (buid, year_of_birth, relationship_to_bu)
    VALUES (%s, %s, %s)
    RETURNING id
    """
    cursor.execute(insert_query, (buid, yob, relationship))
    new_id = cursor.fetchone()[0]
    conn.commit()
    cursor.close()
    return new_id

def update_alumni(alum_id, alum_return, conn):
    """
    Updates an existing alumni record with new information
    If year of birth conflicts, inserts as new record instead (assuming different person with same name)
    """
    name = alum_return.get('name', None)
    yob = alum_return.get('year_of_birth', None)
    relationship = alum_return.get('relationship to BU', None)
    buid = search_buid(name)
    # conn = postgres_connect()
    cursor = conn.cursor()
    # Fix the relationship in predictable ways (e.g. alumni -> student)
    relationship = clean_relationship(relationship)
    # Check that year_of_birth does not conflict with existing
    check_query = """
        SELECT year_of_birth
        FROM Alumni
        WHERE id = %s
    """
    if yob is not None:
        cursor.execute(check_query, (alum_id,))
        existing_yob = cursor.fetchone()[0]
        print(existing_yob, yob)
        if existing_yob is not None and abs(existing_yob - yob) > 2:
            print(f"Warning: Conflicting year_of_birth for alumni ID {alum_id}: existing {existing_yob}, new {yob}. Keeping existing.")
            # Insert into alumni as new
            return insert_alumni(alum_return, conn)
    # Update existing record with new info
    update_query = """
    UPDATE Alumni
    SET buid = COALESCE(buid, %s),
        year_of_birth = COALESCE(year_of_birth, %s),
        relationship_to_bu = COALESCE(relationship_to_bu, %s)
    WHERE id = %s
    """
    cursor.execute(update_query, (buid, yob, relationship, alum_id))
    conn.commit()
    cursor.close()

def upsert_alumni(alum_return, conn):
    name = alum_return.get('name', None)
    existing_alumni = alumni_match(name, conn)
    print(f'Upsert check for {name}, found existing IDs: {existing_alumni}')
    if existing_alumni:
        alum_id = existing_alumni[0][0]
        update_alumni(alum_id, alum_return, conn)
        print(f'Updated existing alumni ID {alum_id} for {name}')
        return alum_id
    else:
        print(f'Inserting new alumni record for {name}')
        return insert_alumni(alum_return, conn)

def insert_bu_name(alum_id, full_name, conn):
    # conn = postgres_connect()
    cursor = conn.cursor()
    insert_query = """
    INSERT INTO Name (alumni_id, full_name)
    VALUES (%s, %s)
    """
    cursor.execute(insert_query, (alum_id, full_name))
    conn.commit()
    cursor.close()

def update_bu_name(alum_id, full_name, conn, force=False):
    # conn = postgres_connect()
    cursor = conn.cursor()
    update_string = "COALESCE(full_name, %s)" if not force else "%s"

    update_query = f"""
    UPDATE Name
    SET full_name = {update_string}
    WHERE alumni_id = %s
    """
    # Two parameters: one for full_name, one for alum_id
    cursor.execute(update_query, (full_name, alum_id))
    conn.commit()
    cursor.close()

def insert_degree(alumni_id, degree_dict, conn):
    school = degree_dict.get('school', None)
    degree_type = degree_dict.get('degree_type', None)
    end_year = degree_dict.get('end_year', None)
    start_year = degree_dict.get('start_year', None)
    cursor = conn.cursor()
    insert_query = """
    INSERT INTO Degree (alumni_id, school, degree_type, start_year, end_year)
    VALUES (%s, %s, %s, %s, %s)
    RETURNING id
    """
    cursor.execute(insert_query, (alumni_id, school, degree_type, start_year, end_year))
    new_id = cursor.fetchone()[0]
    conn.commit()
    cursor.close()
    return new_id

def update_degree(alumni_id, degree_dict, conn):
    """
    If alum only has one degree, update that degree record
    Otherwise, update only if degree_type matches too
    """
    school = degree_dict.get('school', None)
    degree_type = degree_dict.get('degree_type', None)
    end_year = degree_dict.get('end_year', None)
    start_year = degree_dict.get('start_year', None)
    cursor = conn.cursor()
    # Match on degree type
    # check how many degrees alum has
    count_query = """
    SELECT COUNT(*)
    FROM Degree
    WHERE alumni_id = %s
    """
    cursor.execute(count_query, (alumni_id,))
    count = cursor.fetchone()[0]
    if count == 1:
        degree_id_query = """
        SELECT id
        FROM Degree
        WHERE alumni_id = %s
        """
        cursor.execute(degree_id_query, (alumni_id,))
    else:
        degree_id_query = """
        SELECT id
        FROM Degree
        WHERE alumni_id = %s AND degree_type = %s
        """
        cursor.execute(degree_id_query, (alumni_id, degree_type))
    result = cursor.fetchone()
    if not result:
        print(f"No matching degree found for alumni ID {alumni_id} with degree type {degree_type}. Inserting new degree.")
        insert_degree(alumni_id, degree_dict, conn)
        cursor.close()
        return
    degree_id = result[0]
    update_query = """
    UPDATE Degree
    SET school = COALESCE(school, %s),
        degree_type = COALESCE(degree_type, %s),
        start_year = COALESCE(start_year, %s),
        end_year = COALESCE(end_year, %s)
    WHERE id = %s
    """
    cursor.execute(update_query, (school, degree_type, start_year, end_year, degree_id))
    conn.commit()
    cursor.close()

def find_company_by_name(company_name, conn):
    cursor = conn.cursor()
    query = """
    SELECT id
    FROM Companies
    WHERE LOWER(name) = LOWER(%s)
    """
    cursor.execute(query, (company_name,))
    results = cursor.fetchall()
    cursor.close()
    return results

def find_company_by_fuzzy_name(company_name, conn):
    """
    Find a company by a fuzzy name match.
    Not using this yet since company names will need to be normalized a bit to use this well.
    """
    cursor = conn.cursor()
    query = """
    SELECT id, name, levenshtein(LOWER(name), LOWER(%s)) AS sim
    FROM Companies
    WHERE levenshtein(LOWER(name), LOWER(%s)) < GREATEST(LENGTH(%s), LENGTH(name)) / 1.5
    ORDER BY sim DESC
    LIMIT 1
    """
    cursor.execute(query, (company_name, company_name, company_name))
    results = cursor.fetchall()
    cursor.close()
    return results


def find_company_by_cik(cik, conn):
    # conn = postgres_connect()
    cursor = conn.cursor()
    query = """
    SELECT id
    FROM Companies
    WHERE cik = %s
    """
    cursor.execute(query, (cik,))
    results = cursor.fetchall()
    cursor.close()
    print(f'cik results: {results}')
    return results[0][0] if results else None


def insert_or_get_company(company_dict,conn):
    company_name = company_dict.get('company_name', None)
    if company_name is None:
        return None
    company_name = company_name.lower()
    company_cik = company_dict.get('company_cik', None)
    existing = find_company_by_name(company_name, conn)
    if existing:
        return existing[0][0]
    # conn = postgres_connect()
    if company_cik and len(company_cik) != 10:
        company_cik = None
    cursor = conn.cursor()
    insert_query = """
    INSERT INTO Companies (name, cik)
    VALUES (%s, %s)
    RETURNING id
    """
    cursor.execute(insert_query, (company_name, company_cik))
    new_id = cursor.fetchone()[0]
    conn.commit()
    cursor.close()
    return new_id

def populate_companies(tickers, conn):
    client = SECClient(user_agent=load_user_agent_from_env())
    for ticker in tickers:
        cik = ticker.get('cik', None)
        name = ticker.get('name', None)
        if cik and name:
            name = name.lower()
            existing = find_company_by_cik(cik, conn)
            print(f"Processing company CIK {cik}, name {name}. Existing: {existing}")
            if not existing:
                # conn = postgres_connect()
                cursor = conn.cursor()
                insert_query = """
                INSERT INTO Companies (cik, name)
                VALUES (%s, %s)
                """
                cursor.execute(insert_query, (cik, name))
                conn.commit()
                cursor.close()

def clean_employment_years(year_start, year_end):
    """
    Cleans employment years, converting 'present' to current year
    """
    if year_end == 'present':
        year_end = datetime.now().year
    if year_end == 'null':
        year_end = None
    if year_start == 'null':
        year_start = None
    try:
        if year_start is not None:
            year_start = int(year_start)
    except ValueError:
        year_start = None
    try:
        if year_end is not None:
            year_end = int(year_end)
    except ValueError:
        year_end = None
    return year_start, year_end



def alumni_worked_at(alumni_id, company_name, conn):
    """
    Checks if the alumni has worked at the given company
    """
    # conn = postgres_connect()
    cursor = conn.cursor()
    if company_name is None:
        return False
    company_name = company_name.lower()
    query = """
    SELECT COUNT(*)
    FROM Employment_History
    WHERE alumni_id = %s AND company_name = %s
    """
    cursor.execute(query, (alumni_id, company_name))
    result = cursor.fetchone()
    cursor.close()
    return result[0] > 0

def insert_employment_history(alumni_id, employment_dict, conn):
    """
    Inserts a new employment history record into the database
    """
    company_name = employment_dict.get('company_name', None)
    year_start = employment_dict.get('year_start', None)
    year_end = employment_dict.get('year_end', None)
    year_start, year_end = clean_employment_years(year_start, year_end)
    compensation = employment_dict.get('compensation', None)
    location = employment_dict.get('location', None)
    if company_name is None:
        return
    company_name = company_name.lower()
    company_dict = {'company_name': company_name}
    company_id = insert_or_get_company(company_dict, conn)
    # conn = postgres_connect()
    cursor = conn.cursor()
    insert_query = """
    INSERT INTO Employment_History (alumni_id, company_id, company_name, year_start, year_end, location, compensation)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (alumni_id, company_id) DO NOTHING
    """
    try:
        cursor.execute(insert_query, (alumni_id, company_id, company_name, year_start, year_end, location, compensation))
        conn.commit()
    except Exception as e:
        print(f"Error inserting employment history: {e}")
    finally:
        cursor.close()

def update_employment_history(alumni_id, employment_dict, conn):
    """
    Updates an existing employment history record with new information
    """
    year_start = employment_dict.get('year_start', None)
    year_end = employment_dict.get('year_end', None)
    year_start, year_end = clean_employment_years(year_start, year_end)
    compensation = employment_dict.get('compensation', None)
    location = employment_dict.get('location', None)
    company_name = employment_dict.get('company_name', None)
    if company_name is None:
        return
    company_name = company_name.lower()
    # Check if company name is already attached to alumni
    company_dict = {'company_name': company_name}
    company_id = insert_or_get_company(company_dict, conn)
    # conn = postgres_connect()
    cursor = conn.cursor()
    update_query = """
    UPDATE Employment_History
    SET company_id = COALESCE(company_id, %s),
        company_name = COALESCE(company_name, %s),
        year_start = COALESCE(year_start, %s),
        year_end = COALESCE(year_end, %s),
        location = COALESCE(location, %s),
        compensation = COALESCE(compensation, %s)
    WHERE alumni_id = %s AND company_name = %s
    """
    cursor.execute(update_query, (company_id, company_name, year_start, year_end, location, compensation, alumni_id, company_name))
    conn.commit()
    cursor.close()


def insert_filing(alumni_id, file_link, company_name, company_cik, text_extracted, filing_date, conn):
    cursor = conn.cursor()
    # Find company id by name or cik
    company_id = None
    if company_cik:
        company_id = find_company_by_cik(company_cik, conn)
    if not company_id and company_name:
        company_id = insert_or_get_company({'company_name': company_name.lower()}, conn)
    insert_query = """
    INSERT INTO Filings (alumni_id, link, company_id, date, text_extracted)
    VALUES (%s, %s, %s, %s, %s)
    """
    cursor.execute(insert_query, (alumni_id, file_link, company_id, filing_date, text_extracted))
    conn.commit()
    cursor.close()

def update_filing(alumni_id, file_link, company_name, company_cik, text_extracted, filing_date, conn):
    # Concatenate new text_extracted to existing
    cursor = conn.cursor()
    # Find company id by name or cik
    company_id = None
    if company_cik:
        company_id = find_company_by_cik(company_cik, conn)
    if not company_id and company_name:
        company_id = insert_or_get_company({'company_name': company_name.lower()}, conn)
    # Get existing text_extracted
    select_query = """
    SELECT text_extracted
    FROM Filings
    WHERE alumni_id = %s AND link = %s
    """
    cursor.execute(select_query, (alumni_id, file_link))
    result = cursor.fetchone()
    existing_text = result[0] if result else ''
    # Concatenate
    new_text = existing_text + '\n' + text_extracted if existing_text else text_extracted
    update_query = """
    UPDATE Filings
    SET company_id = COALESCE(%s, company_id),
        date = COALESCE(%s, date),
        text_extracted = %s
    WHERE alumni_id = %s AND link = %s
    """
    cursor.execute(update_query, (company_id, filing_date, new_text, alumni_id, file_link))
    conn.commit()
    cursor.close()

if __name__ == "__main__":
    init_schema()
    # populate_companies()