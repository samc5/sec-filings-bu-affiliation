-- Alumni table
CREATE TABLE Alumni (
    id SERIAL PRIMARY KEY,
    buid CHAR(9) UNIQUE NOT NULL,
    year_of_birth INT,
    relationship_to_bu VARCHAR(50) CHECK (relationship_to_bu IN (
        'Student', 'Professor', 'Admin', 'BoardOfTrustees', 'Donor', 'Researcher', 'Business', 'Transitive'
    ))
);

-- Foreign Alumni table
CREATE TABLE Foreign_Alumni (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    school TEXT NOT NULL
);

-- Alumni Relationships table
CREATE TABLE Alumni_Relationships (
    foreign_alumni_id INT REFERENCES Foreign_Alumni(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    buid CHAR(9) NOT NULL, -- not referencing BUID in other table because these are different people
    relationship_with_bu VARCHAR(50) CHECK (relationship_with_bu IN (
        'Student', 'Professor', 'Admin', 'BoardOfTrustees', 'Donor', 'Researcher', 'Vendor'
    )),
    PRIMARY KEY(foreign_alumni_id, name)
);

-- Employment History table
CREATE TABLE Employment_History (

    alumni_id INT REFERENCES Alumni(id) ON DELETE CASCADE,
    company_id INT REFERENCES Companies(id),
    company_name TEXT,
    year_start INT,
    year_end INT,
    location TEXT,
    compensation NUMERIC
);

-- Name table (for alternate or full names)
CREATE TABLE Name (
    alumni_id INT REFERENCES Alumni(id) ON DELETE CASCADE,
    full_name TEXT NOT NULL,
    PRIMARY KEY(alumni_id, full_name)
);

-- Degree table
CREATE TABLE Degree (
    alumni_id INT REFERENCES Alumni(id) ON DELETE CASCADE,
    school TEXT,
    degree_type TEXT,
    start_year INT,
    end_year INT,
    PRIMARY KEY(alumni_id, school, degree_type)
);

-- Companies table
CREATE TABLE Companies (
    id SERIAL PRIMARY KEY,
	cik CHAR(10), -- SEC key, not making this primary key because we may want non-public companies in here
    name TEXT NOT NULL,
    description TEXT,
    date_of_founding DATE,
    latest_filing DATE
);

-- Filings table
CREATE TABLE Filings (
    alumni_id INT REFERENCES Alumni(id) ON DELETE CASCADE,
    foreign_alumni_id INT REFERENCES Foreign_Alumni(id) ON DELETE CASCADE,
    filing_type TEXT,
    link TEXT,
    text_extracted TEXT,
    date DATE,
    PRIMARY KEY(alumni_id, foreign_alumni_id, link)
);
