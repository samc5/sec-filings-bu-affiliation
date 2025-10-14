# Architecture Documentation

## Overview

The SEC Filings toolkit is a Python-based system for downloading, parsing, and analyzing SEC EDGAR filings with specialized functionality for identifying university affiliations in executive and director biographies. The architecture follows a modular design with clear separation of concerns across data retrieval, parsing, and analysis layers.

### Primary Use Case

The system is optimized for identifying individuals with Boston University (BU) affiliations mentioned in SEC filings, particularly in proxy statements (DEF 14A) and annual reports (10-K).

### Key Capabilities

- Rate-limited SEC EDGAR API access (10 requests/second compliance)
- Company and filing metadata retrieval
- HTML/XML parsing and text extraction
- Biographical section identification
- Pattern-based affiliation matching with confidence scoring
- Bulk search across all SEC-registered companies

---

## System Architecture

### Architectural Principles

1. **Layered Architecture**: Clear separation between API client, parser, and domain logic
2. **Defensive Design**: Comprehensive error handling with specific exception types
3. **SEC Compliance**: Built-in rate limiting and User-Agent enforcement
4. **Extensibility**: Pattern-based search allows for customization beyond BU affiliations
5. **Performance**: Session reuse, intelligent caching, and batch processing support

### High-Level Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    User/Application Layer                       │
│                    (examples/, scripts)                         │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Core Business Logic                        │
│  ┌──────────────────┐  ┌─────────────────┐  ┌────────────────┐  │
│  │ SECClient        │  │ FilingParser    │  │ Affiliation    │  │
│  │ (client.py)      │  │ (parser.py)     │  │ Finder         │  │
│  │                  │  │                 │  │ (affiliation_  │  │
│  │ - Rate limiting  │  │ - HTML/XML      │  │  search.py)    │  │
│  │ - API requests   │  │   parsing       │  │                │  │
│  │ - CIK lookup     │  │ - Text          │  │ - Pattern      │  │
│  │ - Filing fetch   │  │   extraction    │  │   matching     │  │
│  │ - Bulk search    │  │ - Bio detection │  │ - Confidence   │  │
│  │                  │  │ - Name parsing  │  │   scoring      │  │
│  └──────────────────┘  └─────────────────┘  └────────────────┘  │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Infrastructure Layer                          │
│  ┌──────────────────┐  ┌─────────────────┐  ┌────────────────┐ │
│  │ Config           │  │ Exceptions      │  │ External APIs  │ │
│  │ (config.py)      │  │ (exceptions.py) │  │                │ │
│  │                  │  │                 │  │ - SEC EDGAR    │ │
│  │ - .env parsing   │  │ - SECAPIError   │  │ - BeautifulSoup│ │
│  │ - User-Agent     │  │ - RateLimitError│  │ - Requests     │ │
│  │   validation     │  │ - Not Found errs│  │                │ │
│  └──────────────────┘  └─────────────────┘  └────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

---

## Core Components

### 1. SECClient (`src/sec_filings/client.py`)

**Purpose**: HTTP client for SEC EDGAR database with rate limiting and compliance features.

**Key Responsibilities**:
- Enforce SEC's 10 requests/second rate limit
- Validate and attach User-Agent headers
- Provide clean API for common SEC operations
- Handle pagination and bulk data retrieval

**Public Methods**:

| Method | Description | Returns |
|--------|-------------|---------|
| `get_cik(ticker)` | Convert ticker symbol to CIK | Zero-padded 10-digit CIK string |
| `get_filings(cik, filing_type, count, before_date)` | Fetch filing list for company | List of filing metadata dicts |
| `download_filing(accession_number, cik, save_path)` | Download filing HTML content | Filing content as string |
| `get_company_tickers_list()` | Fetch all ~13,000 SEC companies | List of company metadata dicts |
| `get_recent_filings_bulk(filing_types, start_date, end_date, max_per_company, company_limit)` | Bulk search across all companies | List of filings with company info |

**Implementation Details**:

```python
# Rate limiting mechanism
self._last_request_time = 0.0
self._min_request_interval = 0.1  # 100ms between requests

def _rate_limit(self):
    elapsed = time.time() - self._last_request_time
    if elapsed < self._min_request_interval:
        time.sleep(self._min_request_interval - elapsed)
    self._last_request_time = time.time()
```

**SEC API Endpoints Used**:
- Browse EDGAR: `/cgi-bin/browse-edgar` (company and filing search)
- Company Tickers: `/files/company_tickers.json` (bulk company list)
- Document Archives: `/Archives/edgar/data/{cik}/{accession}/` (filing downloads)

**Error Handling**:
- `CompanyNotFoundError`: Invalid ticker or CIK
- `FilingNotFoundError`: Invalid accession number
- `RateLimitError`: 429 HTTP status code
- `SECAPIError`: General request failures

---

### 2. FilingParser (`src/sec_filings/parser.py`)

**Purpose**: Extract and structure text from SEC filing HTML/XML documents.

**Key Responsibilities**:
- Detect and parse HTML vs XML formats
- Extract clean text from complex nested HTML
- Identify biographical sections using pattern matching
- Parse individual person biographies from text

**Public Methods**:

| Method | Description | Returns |
|--------|-------------|---------|
| `extract_text_from_html(html_content)` | Clean HTML to plain text | Text string |
| `find_biographical_sections(html_content)` | Locate bio sections in filing | List of section dicts |
| `extract_individual_bios(bio_section_text)` | Parse individual person bios | List of person bio dicts |

**Biographical Section Detection**:

The parser identifies sections using regex patterns:

```python
bio_patterns = [
    (r"Item\s+10\.?\s+Directors[,\s]+Executive Officers", "Item 10: Directors & Officers"),
    (r"(?:BOARD OF DIRECTORS|DIRECTORS AND EXECUTIVE OFFICERS)", "Directors & Officers"),
    (r"(?:EXECUTIVE OFFICERS|MANAGEMENT)", "Executive Officers"),
    (r"(?:BIOGRAPHICAL INFORMATION|BIOGRAPHIES)", "Biographies"),
    (r"(?:PROPOSAL\s+\d+[\s\-]+ELECTION OF DIRECTORS)", "Election of Directors"),
]
```

**Individual Biography Extraction**:

Three-tier fallback strategy:
1. **Primary**: Name + age pattern (e.g., "John Smith, age 45")
2. **Secondary**: Name + title pattern (e.g., "Jane Doe, Director")
3. **Tertiary**: Paragraph-based extraction with name detection

**Text Cleaning Pipeline**:
```
Raw HTML → BeautifulSoup parse → Remove scripts/styles →
Extract text → Normalize whitespace → Clean text
```

---

### 3. UniversityAffiliationFinder (`src/sec_filings/affiliation_search.py`)

**Purpose**: Pattern-based search for university affiliations in biographical text.

**Key Responsibilities**:
- Match university name patterns (case-insensitive)
- Classify affiliation types (degree, position, education, employment, mention)
- Assign confidence scores (high, medium, low)
- Deduplicate similar matches

**Public Methods**:

| Method | Description | Returns |
|--------|-------------|---------|
| `find_affiliations_in_text(text, person_name)` | Search text for affiliations | List of `AffiliationMatch` objects |
| `search_filing(html_content, filing_metadata)` | Search entire filing | List of `AffiliationMatch` objects |
| `deduplicate_matches(matches)` (static) | Remove duplicate matches | Deduplicated list |

**Pattern Categories**:

1. **University Patterns** (default: Boston University):
   - "Boston University"
   - "Boston U."

2. **Degree Patterns**:
   - B.A., B.S., Bachelor's, Master's, M.A., M.B.A., M.S., Ph.D., J.D., M.D., LL.M., LL.B., Ed.D.

3. **Role Patterns**:
   - professor, faculty, instructor, lecturer, researcher, fellow
   - trustee, board member, dean, chair, president, chancellor, provost

**Classification Algorithm**:

```python
def _classify_affiliation(context: str) -> tuple[str, str]:
    # Priority 1: Degree mentions → ("degree", "high")
    if degree_pattern_match:
        return ("degree", "high")

    # Priority 2: Role/position → ("position", "high")
    if role_pattern_match:
        return ("position", "high")

    # Priority 3: Education keywords → ("education", "medium")
    if "studied" or "attended" or "graduated" etc.:
        return ("education", "medium")

    # Priority 4: Employment keywords → ("employment", "medium")
    if "served" or "worked" or "employed" etc.:
        return ("employment", "medium")

    # Default: General mention → ("mention", "low")
    return ("mention", "low")
```

**Context Extraction**:
- Extracts ±200 characters around each university mention
- Provides sufficient context for manual validation
- Truncated to 500 characters in CSV output

---

### 4. Configuration (`src/sec_filings/config.py`)

**Purpose**: Environment-based configuration with validation.

**Key Function**: `load_user_agent_from_env()`

**Configuration Requirements**:
```env
SEC_USER_NAME=Your Name
SEC_USER_EMAIL=your.email@example.com
```

**Validation**:
- Checks for `.env` file existence
- Validates both fields are present
- Ensures email format with "@" symbol
- Exits with helpful error messages if invalid

**User-Agent Format**: `"Name email@example.com"`

---

### 5. Exceptions (`src/sec_filings/exceptions.py`)

**Exception Hierarchy**:

```
SECAPIError (base)
├── RateLimitError (429 response)
├── CompanyNotFoundError (invalid ticker/CIK)
└── FilingNotFoundError (invalid accession number)
```

**Usage Pattern**:
```python
try:
    cik = client.get_cik("INVALID")
except CompanyNotFoundError as e:
    print(f"Company not found: {e}")
except SECAPIError as e:
    print(f"General API error: {e}")
```

---

## Data Flow

### Typical Search Workflow

```
1. Initialize
   └─> load_user_agent_from_env() → Create SECClient → Create UniversityAffiliationFinder

2. Company Discovery
   └─> get_company_tickers_list() → ~13,000 company records

3. Filing Retrieval (per company)
   └─> get_filings(cik, "DEF 14A", count=1) → Filing metadata list

4. Document Download
   └─> download_filing(accession_number) → Raw HTML content

5. Parsing
   └─> find_biographical_sections(html) → Bio sections
       └─> extract_individual_bios(section_text) → Person bios

6. Analysis
   └─> search_filing(html, metadata) → AffiliationMatch objects
       └─> find_affiliations_in_text(bio_text) → Matches with confidence

7. Output
   └─> deduplicate_matches() → CSV export
```

### Data Models

**Filing Metadata Dict**:
```python
{
    "type": str,              # e.g., "DEF 14A"
    "date": str,              # e.g., "2024-03-15"
    "accessionNumber": str,   # e.g., "0000320193-24-000012"
    "url": str,               # Full SEC URL
    "company_name": str,      # Only in bulk search results
    "ticker": str,            # Only in bulk search results
    "cik": str                # Only in bulk search results
}
```

**Company Dict**:
```python
{
    "cik": str,      # Zero-padded 10 digits
    "ticker": str,   # Stock symbol
    "name": str      # Company legal name
}
```

**AffiliationMatch Object**:
```python
@dataclass
class AffiliationMatch:
    person_name: str              # "John Smith"
    affiliation_type: str         # "degree"|"position"|"education"|"employment"|"mention"
    context: str                  # ±200 char excerpt
    confidence: str               # "high"|"medium"|"low"
    filing_info: Dict[str, str]   # Optional filing metadata
```

**Bio Dict**:
```python
{
    "name": str,     # Person's full name
    "age": str,      # Age or "Unknown"
    "bio": str       # Biography text (up to 2000 chars)
}
```

---

## API Design Patterns

### 1. Session Management

All HTTP requests use a persistent `requests.Session`:
```python
self.session = requests.Session()
self.session.headers.update({"User-Agent": user_agent})
```

Benefits:
- Connection pooling and TCP reuse
- Consistent headers across all requests
- Performance improvement for bulk operations

### 2. Rate Limiting Decorator Pattern

Automatic rate limiting via `_rate_limit()` called before every request:
```python
def _make_request(self, url, params=None):
    self._rate_limit()  # Enforces timing
    return self.session.get(url, params=params, timeout=30)
```

### 3. Progressive Fallback

Filing parser uses progressive fallback strategies:
- Try XML parser first if XML detected
- Fall back to lxml (HTML) parser
- Try multiple bio extraction patterns (age → title → paragraph)

### 4. Static Factory Methods

Parser methods are static when no state needed:
```python
FilingParser.extract_text_from_html(content)  # No instance required
```

### 5. Dependency Injection

Finder accepts custom patterns for extensibility:
```python
finder = UniversityAffiliationFinder(
    university_patterns=["Harvard University", "Harvard"]
)
```

---

## Performance Considerations

### Rate Limiting

- **SEC Requirement**: Maximum 10 requests/second
- **Implementation**: 100ms minimum interval between requests
- **Impact**: ~360 requests/minute, ~21,600 requests/hour

### Bulk Search Performance

Searching all SEC companies (year range search):
- ~13,000 companies × 1-2 filing types × 1-2 filings = 13,000-52,000 filings
- Rate-limited to ~360 filings/minute
- **Total time**: 36-144 minutes for comprehensive search

### Optimization Strategies

1. **Test Mode**: `company_limit=50` for development/testing
2. **Periodic Saves**: Save results every 100 matches to prevent data loss
3. **Error Tolerance**: Skip failing companies, continue processing
4. **Progress Tracking**: Regular status updates (every 50 filings)
5. **Session Reuse**: Persistent HTTP connections reduce overhead

---

## Error Handling Strategy

### Layered Error Handling

1. **HTTP Layer** (`SECClient._make_request`):
   - Catches `requests.exceptions.RequestException`
   - Wraps in `SECAPIError`
   - Checks for 429 (rate limit) → `RateLimitError`

2. **Business Logic Layer**:
   - `get_cik()`: Raises `CompanyNotFoundError` if ticker invalid
   - `download_filing()`: Raises `FilingNotFoundError` if not found

3. **Application Layer** (examples):
   - Try/except blocks for individual companies
   - Continue processing on errors
   - Log errors but don't halt bulk operations

### Error Recovery

```python
# Example from search_by_year_range.py
for filing in filings:
    try:
        content = client.download_filing(filing["accessionNumber"])
        matches = finder.search_filing(content, filing)
        all_matches.extend(matches)
    except Exception as e:
        errors += 1
        print(f"Error: {e}")
        # Continue to next filing
```

---

## Dependencies

### Production Dependencies

| Package | Purpose | Key Usage |
|---------|---------|-----------|
| `requests>=2.31.0` | HTTP client | SEC API communication |
| `beautifulsoup4>=4.12.0` | HTML/XML parsing | Filing document parsing |
| `lxml>=4.9.0` | XML parser backend | BeautifulSoup parser |
| `pandas>=2.0.0` | Data manipulation | Optional for CSV processing |

### Development Dependencies

| Package | Purpose |
|---------|---------|
| `pytest>=7.4.0` | Unit testing framework |
| `pytest-cov>=4.1.0` | Code coverage reporting |
| `black>=23.0.0` | Code formatting |
| `flake8>=6.0.0` | Linting |
| `mypy>=1.5.0` | Type checking |

---

## Example Workflows

### Workflow 1: Single Company Search

```python
from sec_filings import SECClient, UniversityAffiliationFinder, load_user_agent_from_env

# Setup
user_agent = load_user_agent_from_env()
client = SECClient(user_agent)
finder = UniversityAffiliationFinder()

# Get company CIK
cik = client.get_cik("AAPL")

# Fetch recent proxy statements
filings = client.get_filings(cik, filing_type="DEF 14A", count=3)

# Search first filing
content = client.download_filing(filings[0]["accessionNumber"])
matches = finder.search_filing(content, filing_metadata=filings[0])

# Results
for match in matches:
    print(f"{match.person_name}: {match.affiliation_type} ({match.confidence})")
```

### Workflow 2: Bulk Year Range Search

```python
# Fetch all companies
companies = client.get_company_tickers_list()  # ~13,000 companies

# Get filings for 2023-2024
filings = client.get_recent_filings_bulk(
    filing_types=["DEF 14A", "10-K"],
    start_date="2023-01-01",
    end_date="2024-12-31",
    max_per_company=1,
    company_limit=None  # All companies
)

# Search each filing
all_matches = []
for filing in filings:
    content = client.download_filing(filing["accessionNumber"])
    matches = finder.search_filing(content, filing_metadata=filing)
    all_matches.extend(matches)

# Deduplicate and export
unique_matches = UniversityAffiliationFinder.deduplicate_matches(all_matches)
# Save to CSV...
```

### Workflow 3: Custom University Search

```python
# Search for MIT affiliations instead
finder = UniversityAffiliationFinder(
    university_patterns=[
        r"Massachusetts Institute of Technology",
        r"MIT\b",  # \b for word boundary
        r"M\.I\.T\.",
    ]
)

# Same search workflow as above
matches = finder.search_filing(content)
```

---

## Extension Points

### 1. Custom University Patterns

Override default BU patterns:
```python
finder = UniversityAffiliationFinder(
    university_patterns=["Your University", "Your U."]
)
```

### 2. Additional Filing Types

Support any SEC filing type:
```python
filings = client.get_filings(cik, filing_type="S-1")  # IPO registrations
filings = client.get_filings(cik, filing_type="8-K")  # Current reports
```

### 3. Custom Biographical Patterns

Extend `FilingParser.find_biographical_sections()` with new patterns:
```python
custom_patterns = [
    (r"ADVISORY BOARD", "Advisory Board"),
    (r"SCIENTIFIC ADVISORS", "Scientific Advisors"),
]
```

### 4. Confidence Score Customization

Modify `_classify_affiliation()` scoring logic:
```python
def _classify_affiliation(self, context):
    # Add custom high-confidence patterns
    if "named professor" in context.lower():
        return ("position", "very_high")
    # ... existing logic
```

---

## Testing Strategy

### Test Structure

```
tests/
├── __init__.py
└── test_client.py        # SECClient unit tests
```

### Key Test Areas

1. **Rate Limiting**: Verify 100ms minimum interval
2. **CIK Lookup**: Test ticker → CIK conversion
3. **Filing Retrieval**: Mock SEC API responses
4. **Parser**: HTML/XML extraction accuracy
5. **Pattern Matching**: Affiliation detection precision/recall

### Running Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=src/sec_filings --cov-report=html

# Specific test file
pytest tests/test_client.py
```

---

## Security Considerations

### User-Agent Privacy

The `.env` file contains user contact information and should never be committed:
```gitignore
.env
```

Example `.env.example` provided for documentation.

### API Key Management

Currently no API keys required. If SEC API access changes:
- Add `SEC_API_KEY` to `.env`
- Load in `config.py`
- Pass via headers in `SECClient`

### Input Validation

- Ticker symbols sanitized before API calls
- CIK format validated (10 digits, zero-padded)
- Accession number format checked
- HTML content parsed with safe `lxml` parser

---

## Future Enhancements

### Potential Improvements

1. **Caching Layer**:
   - Local SQLite database for downloaded filings
   - Cache company ticker list (updated quarterly)
   - Reduce redundant API calls

2. **Asynchronous Processing**:
   - Replace `requests` with `aiohttp`
   - Concurrent filing downloads (respecting rate limits)
   - 10x performance improvement potential

3. **Machine Learning**:
   - Train classifier for affiliation type detection
   - Improve confidence scoring accuracy
   - Named Entity Recognition (NER) for person names

4. **Enhanced Parsing**:
   - XBRL (eXtensible Business Reporting Language) support
   - PDF filing support (via `pdfplumber` or similar)
   - Table extraction for structured data

5. **Database Integration**:
   - PostgreSQL backend for results storage
   - Full-text search capabilities
   - Historical tracking and analytics

6. **Web Interface**:
   - Flask/FastAPI REST API
   - React frontend for search and visualization
   - Real-time progress tracking

---

## Troubleshooting

### Common Issues

**Issue**: `CompanyNotFoundError` for valid ticker

**Solution**:
- Verify ticker spelling
- Check if company is SEC-registered
- Try direct CIK lookup on SEC website

---

**Issue**: `RateLimitError` despite internal rate limiting

**Solution**:
- Check for other processes hitting SEC API
- Increase `_min_request_interval` to 0.15 seconds
- Use test mode to reduce request volume

---

**Issue**: No biographical sections found in filing

**Solution**:
- Try different filing types (DEF 14A usually best)
- Manually inspect filing HTML structure
- Add custom patterns to `find_biographical_sections()`

---

**Issue**: False positives in affiliation matching

**Solution**:
- Use only high-confidence matches
- Review context snippets for validation
- Refine university patterns (add word boundaries)

---

## References

### SEC EDGAR Documentation

- [EDGAR Developer Resources](https://www.sec.gov/developer)
- [EDGAR Filing Types](https://www.sec.gov/forms)
- [Company Tickers JSON](https://www.sec.gov/files/company_tickers.json)

### Key Filing Types for Biographical Data

- **DEF 14A**: Proxy statement - director/executive bios
- **10-K**: Annual report - Item 10 (Directors & Officers)
- **S-1**: IPO registration - Management section

### Python Libraries

- [Requests Documentation](https://requests.readthedocs.io/)
- [Beautiful Soup Documentation](https://www.crummy.com/software/BeautifulSoup/bs4/doc/)
- [lxml Documentation](https://lxml.de/)

---

## Conclusion

The SEC Filings toolkit provides a robust, compliant, and extensible foundation for analyzing SEC filings. Its modular architecture, comprehensive error handling, and pattern-based search capabilities make it suitable for both focused research (single company) and broad analysis (bulk searches across all SEC registrants).

The system's design prioritizes:
- **Compliance**: Strict adherence to SEC rate limits and requirements
- **Reliability**: Graceful error handling and recovery
- **Performance**: Efficient session management and bulk operations
- **Maintainability**: Clear separation of concerns and well-documented code
- **Extensibility**: Easy customization for different use cases

For questions or contributions, refer to the project README and CLAUDE.md files.
