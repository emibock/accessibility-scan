# Setup Guide

Quick start guide for the Accessibility Scanner with PDF support.

## Prerequisites

- Python 3.11 or higher
- pip3 (Python package manager)

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/emibock/accessibility-scan.git
cd accessibility-scan
```

### 2. Create virtual environment

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -e .
```

### 4. Install Playwright browser (for web scanning)

```bash
playwright install chromium
```

### 5. (Optional) Install verapdf for enhanced PDF validation

For comprehensive, industry-standard PDF/UA validation, install verapdf:

**macOS:**
```bash
brew install --cask verapdf
```

**Linux:**
```bash
wget https://software.verapdf.org/releases/verapdf-installer.zip
unzip verapdf-installer.zip
./verapdf-install
```

**Windows:**  
Download from https://verapdf.org/software/

**Verify:**
```bash
verapdf --version
```

**What verapdf provides:**
- Industry-standard PDF/UA compliance checking (ISO 14289-1)
- ~100+ validation rules vs. ~10 built-in checks
- Used by PDF Association and accessibility professionals
- Automatic integration - no configuration needed

**Without verapdf:**  
The scanner still works perfectly using built-in Python checks. verapdf is recommended for comprehensive validation but not required.

### 6. (Optional) Install OCR detection for scanned PDF identification

To automatically detect scanned (image-only) PDFs, install OCR capabilities:

**Install Python packages:**
```bash
pip install -e ".[ocr]"
```

**Install Tesseract OCR:**

**macOS:**
```bash
brew install tesseract
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get install tesseract-ocr
```

**Linux (Fedora/RHEL):**
```bash
sudo dnf install tesseract
```

**Windows:**  
Download from https://github.com/tesseract-ocr/tesseract/wiki

**Verify:**
```bash
tesseract --version
```

**What OCR detection provides:**
- Automatically identifies scanned (image-only) PDFs
- Flags them as CRITICAL violations
- Most severe accessibility barrier - completely unreadable by screen readers
- Provides detailed remediation guidance (run OCR, recreate from source)

**Without OCR detection:**  
The scanner still works perfectly. It just won't automatically flag scanned PDFs - you'll need to check manually.

## Usage

### Web UI (Recommended for beginners)

```bash
accessibility-scan web
```

Then open http://127.0.0.1:5000 in your browser.

#### Features:
- **+ New Web Scan** - Scan websites for WCAG violations
- **+ New PDF Scan** - Scan PDFs for PDF/UA compliance
- **Scan History** - View all past scans with download links

### CLI

#### Web Accessibility Scanning

```bash
# Scan single page
accessibility-scan scan --url https://example.com

# Scan with crawling (discover all pages)
accessibility-scan scan --url https://example.com --crawl --max-pages 50

# Scan with WCAG level selection
accessibility-scan scan --url https://example.com --wcag-level 2.2

# Filter by severity
accessibility-scan scan --url https://example.com --min-severity serious
```

#### PDF Accessibility Scanning

```bash
# Scan local PDF
accessibility-scan scan-pdf --file document.pdf

# Scan remote PDF
accessibility-scan scan-pdf --url https://example.com/report.pdf

# Batch scan from file list
echo "https://example.com/doc1.pdf" > pdfs.txt
echo "/path/to/local/doc2.pdf" >> pdfs.txt
accessibility-scan scan-pdf --batch pdfs.txt

# Filter by severity
accessibility-scan scan-pdf --file report.pdf --min-severity serious
```

## Output Files

All scans generate four output files in the results directory:

1. **violations.csv** - Jira import format with all violations
2. **violations.json** - Full scan data in JSON format
3. **violations.md** - Human-readable Markdown report with detailed remediation steps
4. **jira-tickets.md** - Consolidated tickets (one per violation type)

### Importing to Jira

1. Open your Jira project
2. Go to **Issues → Import Issues**
3. Select **CSV**
4. Upload `violations.csv`
5. Map columns to Jira fields:
   - Summary → Summary
   - Description → Description
   - Severity → Priority (or custom field)
   - Page URL → custom field (optional)
6. Complete import

## Configuration (Optional)

Create `config.yml` for web scanning:

```yaml
# Target
start_url: https://example.com
max_pages: 50

# WCAG version
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

Validate config before running:

```bash
accessibility-scan validate config.yml
```

Then use it:

```bash
accessibility-scan scan --config config.yml --crawl
```

## Troubleshooting

### "externally-managed-environment" error

If you see this error during installation, you're using a system Python. Solution:

```bash
# Create and use a virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate
pip install -e .
```

### Web UI won't start

Make sure you're in the virtual environment:

```bash
source venv/bin/activate  # Run this first
accessibility-scan web
```

### Playwright browser not found

Install the Chromium browser:

```bash
playwright install chromium
```

### PDF scanning fails with "module not found"

Ensure you installed the package with PDF dependencies:

```bash
pip install -e .
```

The dependencies include:
- pikepdf (PDF parsing)
- pdfplumber (content extraction)
- httpx (remote PDF downloads)

## Development

### Install with dev dependencies

```bash
pip install -e ".[dev]"
```

### Run code formatting

```bash
black src/
```

### Run linting

```bash
ruff check src/
```

## Next Steps

- Check out the [README](README.md) for detailed feature documentation
- See [CHANGELOG](CHANGELOG.md) for version history
- Review example PDFs with known issues to understand violation types
- Explore the detailed remediation guidance in Markdown reports

## Need Help?

- **GitHub Issues**: https://github.com/emibock/accessibility-scan/issues
- **Documentation**: Check README.md and inline help text in violations.md reports
