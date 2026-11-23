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

## Enhanced PDF Validation with verapdf

The scanner includes **optional integration with verapdf**, the industry-standard PDF/UA validator developed by the PDF Association.

### Why Use verapdf?

**Built-in Python checks** (always available):
- Fast, no external dependencies
- Covers most common accessibility issues
- Good for quick scans and CI/CD pipelines

**verapdf validation** (optional, more comprehensive):
- Industry-standard PDF/UA compliance checking
- Validates against official ISO 14289-1 specification
- More detailed rule coverage (~100+ validation rules)
- Used by PDF Association and accessibility professionals

### Installing verapdf

**macOS (Homebrew):**
```bash
brew install --cask verapdf
```

**Linux:**
```bash
# Download latest release from https://github.com/veraPDF/veraPDF-apps/releases
wget https://software.verapdf.org/releases/verapdf-installer.zip
unzip verapdf-installer.zip
./verapdf-install
```

**Windows:**
Download installer from https://verapdf.org/software/

**Verify installation:**
```bash
verapdf --version
```

### Using verapdf

verapdf integration is **automatic** - if installed, it will be used by default.

**Disable verapdf** (use Python checks only):
```bash
# Via config file
echo "use_verapdf: false" >> config.yml
accessibility-scan scan-pdf --config config.yml --file document.pdf
```

**Choose validation profile:**
```yaml
# config.yml
use_verapdf: true
verapdf_profile: "PDFUA-1"  # or "WCAG-2-1", "WCAG-2-2"
```

**Check if verapdf is being used:**
The scan results will indicate which validator was used:
- `"validator": "verapdf"` - verapdf was used
- No validator field - Python-based checks were used

### Fallback Behavior

If verapdf fails or times out (>60s), the scanner automatically falls back to Python-based checks with no loss of functionality.

## Scanned PDF Detection

The scanner can automatically **detect scanned (image-only) PDFs** using OCR analysis. Scanned PDFs are fundamentally inaccessible - they appear completely blank to screen readers.

### Why Detect Scanned PDFs?

**The Problem:**
- Scanned PDFs are images, not text
- Screen readers cannot read them at all
- Most severe accessibility barrier in PDFs
- Often overlooked until users report issues

**The Solution:**
- Automatic detection using OCR comparison
- Flags scanned PDFs as CRITICAL violations
- Provides detailed remediation guidance
- Prevents distribution of inaccessible documents

### How It Works

The detector:
1. Extracts embedded text from PDF (what screen readers see)
2. Renders PDF pages as images
3. Runs OCR (Tesseract) on images (what humans see)
4. Compares the two: significantly more OCR text = scanned PDF

### Installing OCR Detection

**1. Install Python packages:**
```bash
pip install -e ".[ocr]"
```

This installs:
- `Pillow` - Image processing
- `pytesseract` - Python wrapper for Tesseract OCR

**2. Install Tesseract OCR:**

**macOS:**
```bash
brew install tesseract
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get update
sudo apt-get install tesseract-ocr
```

**Linux (Fedora/RHEL):**
```bash
sudo dnf install tesseract
```

**Windows:**
Download installer from https://github.com/tesseract-ocr/tesseract/wiki

**Verify installation:**
```bash
tesseract --version
```

### Using OCR Detection

OCR detection is **automatic** when available:

```bash
# Automatically detects scanned PDFs
accessibility-scan scan-pdf --file document.pdf
```

**Disable OCR detection:**
```yaml
# config.yml
detect_scanned: false
```

**Output when scanned PDF detected:**
```
✗ CRITICAL: pdf-scanned-document
  PDF appears to be a scanned image without a text layer
  
  Detection: 45 chars embedded vs 2,847 chars via OCR (95% confidence)
  
  FIX: Run OCR + remediation in Adobe Acrobat Pro
       Or recreate from source document
```

### What Gets Flagged

**Flagged as scanned (CRITICAL):**
- Pure image PDFs with no text layer
- PDFs with minimal text (<10% of OCR-detected text)
- High confidence detections (>80%)

**Not flagged:**
- PDFs with proper text layer
- PDFs with mostly selectable text
- Low confidence detections (<50%)

### Without OCR Detection

The scanner still works perfectly without OCR detection - it just won't automatically flag scanned PDFs. All other PDF checks (tagging, language, forms, etc.) still run normally.

**When OCR unavailable:**
- No CRITICAL violation for scanned PDFs
- Other accessibility issues still detected
- Manual inspection needed for scanned documents

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
