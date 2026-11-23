# Accessibility Scanner

WCAG 2.0, 2.1, and 2.2 web accessibility scanner **+ PDF/UA compliance checker** with Jira-ready exports (CSV, JSON, Markdown).

## Features

### Web Accessibility Scanning
- **WCAG 2.0, 2.1, and 2.2 scanning** using axe-core
- **Configurable WCAG level** - choose which version to test against
- **Automatic crawling** to discover pages
- **Authentication support** for login-gated apps

### PDF Accessibility Scanning
- **PDF/UA compliance checking** using pikepdf
- **Local file and URL support** - scan uploaded PDFs or remote files
- **Batch scanning** - process multiple PDFs at once
- **Core accessibility checks**:
  - Tagged PDF structure
  - Document language and title metadata
  - Form field labels
  - Bookmarks/TOC for long documents
  - Images and tables (manual review flagged)

### Common Features
- **Multiple export formats**:
  - CSV for Jira bulk import
  - JSON for API automation
  - Markdown for readable reports
- **Web UI** for easy scanning
- **CLI** for automation/CI

## Installation

```bash
pip install -e .
playwright install chromium
```

## Quick Start

### Web UI

```bash
accessibility-scan web
```

Then open http://127.0.0.1:5000

Features:
- **Scan History**: View all past scans on the homepage
- **Rerun Scans**: Click "Rerun" to prefill form with previous scan config
- **Download Reports**: Get CSV, JSON, or Markdown from history or results page

### CLI

Scan single page:
```bash
accessibility-scan scan --url https://example.com
```

Scan with crawling:
```bash
accessibility-scan scan --config config.yml --crawl --output ./results
```

### PDF Scanning

Scan local PDF:
```bash
accessibility-scan scan-pdf --file document.pdf
```

Scan remote PDF:
```bash
accessibility-scan scan-pdf --url https://example.com/report.pdf
```

Batch scan multiple PDFs:
```bash
# Create a text file with PDF paths/URLs (one per line)
echo "https://example.com/doc1.pdf" > pdfs.txt
echo "https://example.com/doc2.pdf" >> pdfs.txt
echo "/path/to/local/doc3.pdf" >> pdfs.txt

accessibility-scan scan-pdf --batch pdfs.txt --output ./pdf-results
```

Filter by severity:
```bash
accessibility-scan scan-pdf --file report.pdf --min-severity serious
```

## Configuration

Create `config.yml`:

```yaml
# Target
start_url: https://example.com
max_pages: 50

# WCAG version (2.0, 2.1, or 2.2)
# Default: 2.2 (recommended)
wcag_level: "2.2"

# Authentication (optional)
authentication:
  login_url: https://example.com/login
  username: ${ENV:USERNAME}
  password: ${ENV:PASSWORD}
  username_selector: input[name='username']
  password_selector: input[name='password']
  submit_selector: button[type='submit']
  success_indicator: .user-menu

# Browser
headless: true
```

Environment variables with `${ENV:VAR_NAME}` are expanded automatically.

**Validate config before running:**

```bash
accessibility-scan validate config.yml
```

Checks for required fields, valid URLs, and auth configuration.

## Output Formats

### CSV (Jira Import)

**Web Scan Columns:**
- Summary (issue title)
- Description (violation details)
- Page URL
- Severity (CRITICAL/SERIOUS/MODERATE/MINOR)
- WCAG Criterion
- Element (HTML)
- Help URL

**PDF Scan Columns:**
- Summary (issue title)
- Description (violation details)
- Source (file:// or https://)
- File Name
- PDF Version
- Page Count
- Severity (CRITICAL/SERIOUS/MODERATE/MINOR)
- WCAG Criterion
- Element (PDF structure path)
- Help URL

Import into Jira:
1. Go to Issues → Import Issues
2. Select CSV
3. Map columns to Jira fields
4. Complete import

### JSON (API/Automation)

Full scan results with metadata:
```json
{
  "scan_date": "2026-09-29T...",
  "total_pages": 10,
  "total_violations": 47,
  "pages": [...]
}
```

### Markdown (Readable Report)

Formatted report with violations grouped by page, including:
- Severity badges
- WCAG criteria
- Affected elements
- Help links

## CLI Commands

```bash
# Validate config before scanning
accessibility-scan validate config.yml

# Scan single URL
accessibility-scan scan --url https://example.com

# Scan with config file
accessibility-scan scan --config config.yml

# Scan with crawling
accessibility-scan scan --config config.yml --crawl

# Specify WCAG level
accessibility-scan scan --url https://example.com --wcag-level 2.2

# Filter by minimum severity
accessibility-scan scan --url https://example.com --min-severity serious

# Custom output directory
accessibility-scan scan --url https://example.com --output ./my-results

# Start web UI
accessibility-scan web

# Custom web UI port
accessibility-scan web --port 8080 --host 0.0.0.0
```

### WCAG Level Selection

Choose which WCAG version to test against:

- `--wcag-level 2.2` - WCAG 2.2 (recommended, default)
- `--wcag-level 2.1` - WCAG 2.1
- `--wcag-level 2.0` - WCAG 2.0

Each level includes conformance levels A and AA. Higher versions include all rules from previous versions plus new success criteria.

### Severity Filtering

Export only violations meeting minimum severity threshold:

- `--min-severity minor` - Include all violations (default)
- `--min-severity moderate` - Exclude minor
- `--min-severity serious` - Exclude minor and moderate
- `--min-severity critical` - Only critical violations

Useful for Jira imports to reduce noise.

## PDF Accessibility Checks

The PDF scanner performs the following compliance checks:

### Automated Checks

✅ **Tagged PDF Structure** (CRITICAL)
- Verifies PDF has proper structure tree and MarkInfo
- Required for screen readers to navigate content

✅ **Document Language** (SERIOUS)
- Checks if document language is specified
- Ensures correct speech synthesis and pronunciation

✅ **Document Title** (SERIOUS)
- Verifies title metadata is present
- Helps users identify documents

✅ **Form Field Labels** (SERIOUS)
- Checks form fields have labels or tooltips
- Required for accessible form filling

✅ **Bookmarks/TOC** (MODERATE)
- Checks for navigation bookmarks (documents >10 pages)
- Improves navigation for all users

### Manual Review Flagged

⚠️ **Images** (SERIOUS)
- Detects images but cannot verify alt text automatically
- Flagged for manual review with Adobe Acrobat Pro or similar

⚠️ **Tables** (MODERATE)
- Detects tables but cannot verify header structure automatically
- Flagged for manual review to confirm TH/TD markup

### Not Yet Implemented

⏳ **Heading Hierarchy** - Complex structure tree analysis
⏳ **Reading Order** - Requires deep structure parsing
⏳ **Color Contrast** - Limited without rendering PDF

**Note:** For comprehensive PDF/UA validation, consider using [veraPDF](https://verapdf.org/) in addition to this tool. The scanner focuses on the most common and critical accessibility issues that can be detected programmatically.

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Format code
black src/

# Lint
ruff check src/
```

## License

Apache 2.0
