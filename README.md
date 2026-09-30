# Accessibility Scanner

WCAG 2.1 accessibility scanner with Jira-ready exports (CSV, JSON, Markdown).

## Features

- **WCAG 2.1 scanning** using axe-core
- **Automatic crawling** to discover pages
- **Multiple export formats**:
  - CSV for Jira bulk import
  - JSON for API automation
  - Markdown for readable reports
- **Web UI** for easy scanning
- **CLI** for automation/CI
- **Authentication support** for login-gated apps

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

## Configuration

Create `config.yml`:

```yaml
# Target
start_url: https://example.com
max_pages: 50

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

Columns:
- Summary (issue title)
- Description (violation details)
- Page URL
- Severity (CRITICAL/SERIOUS/MODERATE/MINOR)
- WCAG Criterion
- Element (HTML)
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

# Filter by minimum severity
accessibility-scan scan --url https://example.com --min-severity serious

# Custom output directory
accessibility-scan scan --url https://example.com --output ./my-results

# Start web UI
accessibility-scan web

# Custom web UI port
accessibility-scan web --port 8080 --host 0.0.0.0
```

### Severity Filtering

Export only violations meeting minimum severity threshold:

- `--min-severity minor` - Include all violations (default)
- `--min-severity moderate` - Exclude minor
- `--min-severity serious` - Exclude minor and moderate
- `--min-severity critical` - Only critical violations

Useful for Jira imports to reduce noise.

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
