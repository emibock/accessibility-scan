# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added - Four New Quick Win Automation Checks

Enhanced both web and PDF scanners with four additional automated checks that catch common accessibility issues:

#### 1. Link Text Quality Checker (Web + PDF) - MODERATE
**What it detects:**
- Generic link text: "click here", "read more", "here", "more"
- URLs as link text: "https://example.com/very/long/url"
- Non-descriptive phrases: "link", "download", "next"
- Single character or number links: "1", "a", "→"

**Why it matters:**
Screen reader users navigate by jumping between links. Generic link text like "click here" provides no context about the destination.

**Example violations:**
```
✗ MODERATE: 8 of 23 links have non-descriptive text
  - "click here" (3 occurrences)
  - "https://example.com/product/details/12345" (1 occurrence)
  - "read more" (4 occurrences)
```

**Applies to:** Both web and PDF scans

---

#### 2. PDF Security/Encryption Check - CRITICAL
**What it detects:**
- Password-protected PDFs
- Encryption with restrictive permissions
- "Content extraction disabled" settings
- Security settings that may block screen readers

**Why it matters:**
Encrypted PDFs with restrictive permissions can completely block screen readers from accessing content, making documents entirely inaccessible regardless of other accessibility features.

**Critical barrier:**
This is flagged as CRITICAL because it can prevent screen readers from functioning at all. Must be fixed before addressing any other PDF accessibility issues.

**Example violation:**
```
✗ CRITICAL: PDF encryption detected - may block assistive technology
  Check File → Properties → Security
  Ensure "Content Extraction for Accessibility: Allowed"
```

**Applies to:** PDF scans only

---

#### 3. PDF Accessibility Metadata - MODERATE/MINOR
**What it detects:**
- `/Suspects` flag = True (indicates known issues)
- `/Marked` flag = False (document not marked as tagged)
- Missing PDF/UA identifier in metadata
- Accessibility API support flags

**Severity levels:**
- **MODERATE**: /Suspects flag or /Marked issues (indicates problems)
- **MINOR**: Missing PDF/UA identifier (nice to have for formal compliance)

**Why it matters:**
Metadata flags help identify PDFs that were created without accessibility in mind and may have issues that need investigation.

**Example violations:**
```
✗ MODERATE: PDF accessibility metadata indicates potential problems
  - /Suspects flag is True (document may have accessibility issues)

✗ MINOR: PDF accessibility metadata could be improved (nice to have)
  - No PDF/UA identifier found in metadata
```

**Applies to:** PDF scans only

---

#### 4. Web Generic Alt Text Detection - MODERATE
**What it detects:**
- Filenames as alt text: "image.jpg", "IMG_1234.png"
- Generic words: "image", "photo", "graphic"
- Placeholder text: "alt text", "todo"
- Very short text: "1", "a"
- URLs or file paths

**Why it matters:**
axe-core catches *missing* alt text, but doesn't flag alt text that's technically present but completely non-descriptive. This check catches what axe misses.

**Example violations:**
```
✗ MODERATE: 5 images have generic alt text
  - "image.jpg" on /assets/product-photo.jpg
    Issue: Uses filename instead of description
  - "photo1" on /images/team.png
    Issue: Generic label with no actual description
```

**Applies to:** Web scans only

---

### Technical Implementation

**Shared utility module:** `src/accessibility_scan/alt_text_checker.py`
- `is_generic_link_text()` - Pattern matching for bad link text
- `is_generic_alt_text()` - Pattern matching for bad alt text  
- Quality message generators with context-specific guidance
- Reusable across web and PDF scanners

**Integration points:**
- **PDF scanner:** New checks in `_check_link_text_quality()`, `_check_security_restrictions()`, `_check_accessibility_metadata()`
- **Web scanner:** Post-processing in `_check_generic_alt_text()` after axe-core scan

**Severity Guidelines:**
- **CRITICAL** - Completely blocks access (e.g., encryption blocking screen readers)
- **SERIOUS** - Major barrier to accessibility (e.g., missing alt text)
- **MODERATE** - Usability issue, should be fixed (e.g., generic text)
- **MINOR** - Best practice, nice to have (e.g., missing metadata)

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
