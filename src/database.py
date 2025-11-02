import psycopg
import os
import dotenv
from sec_filings import SECClient, load_user_agent_from_env
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

def init_schema():
    conn = postgres_connect()
    cursor = conn.cursor()
    with open('../schema.sql', 'r') as f:
        cursor.execute(f.read())
    conn.commit()
    cursor.close()
    conn.close()

def alumni_match(full_name):
    conn = postgres_connect()
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
    conn.close()
    return results

def search_buid(alumni_name):
    return None

def insert_alumni(alum_return):
    name = alum_return.get('full_name', None)
    yob = alum_return.get('year_of_birth', None)
    relationship = alum_return.get('relationship to BU', None)
    buid = search_buid(name)
    conn = postgres_connect()
    cursor = conn.cursor()
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
    conn.close()
    return new_id

def insert_name(alum_type, alum_id, full_name):
    conn = postgres_connect()
    cursor = conn.cursor()
    if alum_type == 'BU':
        insert_query = """
        INSERT INTO Name (alumni_id, full_name)
        VALUES (%s, %s)
        """
    else:
        insert_query = """
        INSERT INTO Foreign_Name (foreign_alumni_id, full_name)
        VALUES (%s, %s)
        """
    cursor.execute(insert_query, (alum_id, full_name))
    conn.commit()
    cursor.close()
    conn.close()

def insert_degree(alumni_id, degree_dict):
    school = degree_dict.get('school', None)
    degree_type = degree_dict.get('degree_type', None)
    end_year = degree_dict.get('end_year', None)
    start_year = degree_dict.get('start_year', None)
    conn = postgres_connect()
    cursor = conn.cursor()
    insert_query = """
    INSERT INTO Degree (alumni_id, school, degree_type, start_year, end_year)
    VALUES (%s, %s, %s, %s, %s)
    """
    cursor.execute(insert_query, (alumni_id, school, degree_type, start_year, end_year))
    conn.commit()
    cursor.close()

def find_company_by_name(company_name):
    conn = postgres_connect()
    cursor = conn.cursor()
    query = """
    SELECT id
    FROM Companies
    WHERE LOWER(name) LIKE LOWER(%s)
    """
    cursor.execute(query, (company_name,))
    results = cursor.fetchall()
    cursor.close()
    conn.close()
    return results

def find_company_by_cik(cik):
    conn = postgres_connect()
    cursor = conn.cursor()
    query = """
    SELECT id
    FROM Companies
    WHERE cik = %s
    """
    cursor.execute(query, (cik,))
    results = cursor.fetchall()
    cursor.close()
    conn.close()
    return results[0][0] if results else None


def insert_or_get_company(company_name):
    existing = find_company_by_name(company_name)
    if existing:
        return existing[0][0]
    conn = postgres_connect()
    cursor = conn.cursor()
    insert_query = """
    INSERT INTO Companies (name)
    VALUES (%s)
    RETURNING id
    """
    cursor.execute(insert_query, (company_name,))
    new_id = cursor.fetchone()[0]
    conn.commit()
    cursor.close()
    conn.close()
    return new_id

def populate_companies():
    client = SECClient(user_agent=load_user_agent_from_env())
    tickers = client.get_company_tickers_list()
    for ticker in tickers:
        cik = ticker.get('cik', None)
        name = ticker.get('name', None)
        if cik and name:
            name = name.lower()
            existing = find_company_by_cik(cik)
            print(f"Processing company CIK {cik}, name {name}. Existing: {existing}")
            if not existing:
                conn = postgres_connect()
                cursor = conn.cursor()
                insert_query = """
                INSERT INTO Companies (cik, name)
                VALUES (%s, %s)
                """
                cursor.execute(insert_query, (cik, name))
                conn.commit()
                cursor.close()
                conn.close()


def insert_employment_history(alumni_id, employment_dict):
    company_name = employment_dict.get('company_name', None)
    year_start = employment_dict.get('year_start', None)
    year_end = employment_dict.get('year_end', None)
    if year_end == 'present':
        year_end = datetime.now().year
    compensation = employment_dict.get('compensation', None)
    location = employment_dict.get('location', None)
    if company_name is None:
        return
    company_name = company_name.lower()
    company_id = insert_or_get_company(company_name)
    conn = postgres_connect()
    cursor = conn.cursor()
    insert_query = """
    INSERT INTO Employment_History (alumni_id, company_id, company_name, year_start, year_end, location, compensation)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    """
    cursor.execute(insert_query, (alumni_id, company_id, company_name, year_start, year_end, location, compensation))
    conn.commit()
    cursor.close()
    conn.close()

def insert_filing(alumni_id, file_link):
    # just alumni id and link for now
    conn = postgres_connect()
    cursor = conn.cursor()
    insert_query = """
    INSERT INTO Filings (alumni_id, file_link)
    VALUES (%s, %s)
    """
    cursor.execute(insert_query, (alumni_id, file_link))
    conn.commit()
    cursor.close()
    conn.close()


def drop_all_tables(not_companies=True):
    conn = postgres_connect()
    cursor = conn.cursor()
    drop_query = """
    DROP TABLE IF EXISTS Name CASCADE;
    DROP TABLE IF EXISTS Foreign_Name CASCADE;
    DROP TABLE IF EXISTS Alumni CASCADE;
    DROP TABLE IF EXISTS Alumni_Relationships CASCADE;
    DROP TABLE IF EXISTS Foreign_Alumni CASCADE;
    DROP TABLE IF EXISTS Degree CASCADE;
    DROP TABLE IF EXISTS Filings CASCADE;
    DROP TABLE IF EXISTS Foreign_Filings CASCADE;
    DROP TABLE IF EXISTS Employment_History CASCADE;
    """
    if not not_companies:
        drop_query += """
        DROP TABLE IF EXISTS Companies CASCADE;
        """
    cursor.execute(drop_query)
    conn.commit()
    cursor.close()
    conn.close()


if __name__ == "__main__":
    drop_all_tables()
    init_schema()
    # populate_companies()