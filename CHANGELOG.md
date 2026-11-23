# Changelog

All notable changes to this project will be documented in this file.

## [0.2.0] - 2026-11-23

### Added - PDF Accessibility Scanning

**Major Feature:** Comprehensive PDF/UA compliance checking with structure tree analysis and optional verapdf integration

#### Core Features
- PDF scanning via CLI and Web UI
- Local file upload, URL scanning, and batch processing
- Structure tree analysis for accurate validation (not just detection)
- Detailed remediation guidance with multi-tool instructions
- Same export formats as web scanning (CSV, JSON, Markdown, Jira tickets)

#### PDF Accessibility Checks (11 automated)
1. **Tagged Structure** (CRITICAL) - Verifies PDF has proper accessibility tags
2. **Document Language** (SERIOUS) - Checks /Lang property is set
3. **Document Title** (SERIOUS) - Validates title metadata and DisplayDocTitle
4. **Table Structure** (SERIOUS) - Analyzes structure tree for TH/TD tags and proper markup
5. **Heading Hierarchy** (MODERATE) - Validates H1→H2→H3 progression, no skipped levels
6. **Form Field Labels** (SERIOUS) - Checks all AcroForm fields have TU/T properties
7. **Bookmarks/TOC** (MODERATE) - Validates Outlines with page-based recommendations
8. **Image Alt Text** (SERIOUS) - Verifies Figure tags have /Alt property in structure tree
9. **Generic Alt Text** (MODERATE) - Detects non-descriptive alt text (filenames, "image", etc.)
10. **Table Detection** (MODERATE) - Visual detection as fallback when not in structure tree
11. **Document Structure** (varies) - Additional metadata and structure validation

#### Enhanced Violation Reports
Each violation now includes:
- **Specific locations** - Exact pages, field numbers, element paths
- **Multi-tool fixes** - Adobe Acrobat Pro, Microsoft Word, LibreOffice, pikepdf (Python)
- **Step-by-step instructions** - Numbered procedures for each tool
- **Best practices** - Guidelines and common pitfalls
- **Code examples** - Working Python snippets for automation
- **Technical details** - Exact PDF properties, expected vs. actual values
- **User impact** - "What this fixes" explanations for each violation

#### CLI Usage
```bash
# Scan local PDF
accessibility-scan scan-pdf --file document.pdf

# Scan remote PDF
accessibility-scan scan-pdf --url https://example.com/report.pdf

# Batch scan multiple PDFs
accessibility-scan scan-pdf --batch pdfs.txt --output ./results

# Filter by severity
accessibility-scan scan-pdf --file report.pdf --min-severity serious
```

#### Web UI Enhancements
- New "+ New PDF Scan" button (red badge)
- File upload with drag-and-drop support
- URL and batch URL input
- Scan history shows type badges (WEB/PDF)
- Target column adapts to scan type (URL for web, "X PDF(s)" for PDF)
- Rerun button routes to correct form type

#### Optional verapdf Integration
- **Automatic detection**: Uses verapdf if installed, graceful fallback if not
- **Industry-standard validation**: ISO 14289-1 PDF/UA compliance (~100+ rules)
- **Zero configuration**: Works out of the box when verapdf is available
- **Configurable**: Can disable or change validation profile
- **Robust fallback**: Automatically uses Python checks on timeout/error
- **Installation**: Optional - `brew install --cask verapdf` (macOS)

**verapdf Benefits:**
- Official PDF/UA validator by PDF Association
- More comprehensive than built-in checks (100+ vs 10 rules)
- Supports PDFUA-1, WCAG-2-1, WCAG-2-2 profiles
- Used by accessibility professionals worldwide

**Configuration Options:**
```yaml
use_verapdf: true          # Default: true (auto-detect)
verapdf_profile: "PDFUA-1" # or "WCAG-2-1", "WCAG-2-2"
```

**Fallback Behavior:**
- verapdf not installed → Python checks (seamless)
- verapdf timeout (>60s) → Python checks (automatic)
- verapdf error → Python checks (with warning)

#### Optional Scanned PDF Detection (OCR)
- **Automatic detection**: Identifies image-only PDFs using OCR comparison
- **Critical barrier**: Scanned PDFs appear completely blank to screen readers
- **Detailed analysis**: Compares embedded text vs OCR-detected text
- **Confidence scoring**: Reports detection confidence and sample details
- **Installation**: Optional - `pip install -e ".[ocr]"` + `brew install tesseract`

**How OCR Detection Works:**
1. Extracts embedded text from PDF (what screen readers see)
2. Renders PDF pages as images at 150 DPI
3. Runs Tesseract OCR on images (what humans see)
4. Compares: OCR >> embedded = scanned PDF
5. Reports confidence level and statistics

**Detection Criteria:**
- Embedded text < 10% of OCR-detected text = SCANNED
- OCR must find >100 characters (avoid false positives)
- Samples first, middle, last pages by default
- Confidence score based on text ratio

**Configuration Options:**
```yaml
detect_scanned: true  # Default: true (auto-detect if available)
```

**Violation Output:**
```
✗ CRITICAL: pdf-scanned-document
  Embedded text: 45 characters
  OCR detected: 2,847 characters  
  Pages sampled: 3 of 15
  Confidence: 95%
```

**Remediation Guidance:**
- Adobe Acrobat Pro: Scan & OCR → Add Tags → Full accessibility check
- ABBYY FineReader: Professional OCR + PDF/UA export
- Recreate from source document (best quality)
- Manual retyping for short documents

**Fallback Behavior:**
- Pillow not installed → OCR detection disabled
- pytesseract not installed → OCR detection disabled
- Tesseract binary not found → OCR detection disabled
- All other PDF checks run normally regardless

#### Dependencies Added
- `pikepdf>=9.0.0` - PDF structure tree parsing and analysis
- `pdfplumber>=0.11.0` - Content extraction and table detection
- `httpx>=0.27.0` - Async HTTP client for downloading remote PDFs
- `verapdf` (optional) - Industry-standard PDF/UA validator
- `Pillow>=10.0.0` (optional: "ocr" extra) - Image processing for OCR
- `pytesseract>=0.3.10` (optional: "ocr" extra) - Tesseract OCR wrapper
- `tesseract` (optional system install) - OCR engine for scanned PDF detection

#### Technical Implementation
- **Structure tree analysis** - Recursively parses PDF accessibility layer
- **Table validation** - Verifies TH (headers) vs TD (data) cell markup
- **Heading hierarchy** - Checks H1-H6 progression and nesting
- **Form field inspection** - Validates tooltip (TU) and name (T) properties
- **Graceful error handling** - Falls back to detection-only on parse errors
- **Async scanning** - Uses asyncio for efficient multi-PDF processing

#### Enhanced Image Alt Text Checking
- **Structure tree verification**: Actually checks if Figure tags have /Alt property
- **Generic alt text detection**: Flags non-descriptive patterns (filenames, "image", etc.)
- **Two severity levels**: Missing alt text (SERIOUS) vs Generic alt text (MODERATE)
- **Specific violations**: Lists exact figures with issues, not bulk "manual review"
- **Shared utility module**: Reusable pattern detection for web and PDF scanners

**Before:**
```
⚠️ PDF contains 15 images - manual review needed
```

**After:**
```
✗ SERIOUS: 3 of 15 images lack alternative text
  Missing: Figure 1, Figure 3, Figure 5

✗ MODERATE: 2 images have generic alt text
  Figure 2: "image.jpg" (uses filename)
  Figure 4: "photo1" (generic label)
```

**Generic Patterns Detected:**
- Filenames: "image.jpg", "IMG_1234.png", "photo.gif"
- Generic words: "image", "photo", "graphic", "figure"
- Placeholders: "alt text", "todo", "placeholder"
- Very short: "1", "a", "2"
- URLs or file paths

**Shared Module (alt_text_checker.py):**
- `is_generic_alt_text()` - Detects bad patterns
- `get_alt_text_quality_message()` - Explains the issue
- `get_better_alt_text_examples()` - Context-specific guidance

### Changed
- **Enhanced PDF image checking** from placeholder to structure tree analysis
- Updated README with PDF scanning documentation
- Enhanced exporter to handle both web and PDF results
- Modified history template to show scan type and appropriate targets
- Updated pyproject.toml description to mention PDF scanning

### Fixed
- History page crash when viewing PDF scan metadata
- Rerun button now routes correctly based on scan type

---

## [0.1.0] - 2026-11-13

### Added
- Initial release
- WCAG 2.0, 2.1, 2.2 web accessibility scanning
- Automatic page crawling
- Authentication support
- CSV, JSON, Markdown exports
- Jira-ready consolidated ticket format
- Web UI with scan history
- CLI with validation command

### Features
- axe-core powered WCAG violation detection
- Configurable WCAG level selection
- Min-severity filtering
- Progress tracking and reporting
- Rerun previous scans from history
