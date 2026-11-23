"""PDF/UA accessibility scanning using pikepdf and pdfplumber"""

import asyncio
from pathlib import Path
from typing import Callable, Dict, List, Optional
import tempfile
import httpx
import pikepdf
import pdfplumber

from .verapdf_validator import VeraPDFValidator
from .ocr_detector import ScannedPDFDetector
from .alt_text_checker import is_generic_alt_text, get_alt_text_quality_message


class PDFAccessibilityScanner:
    """Scanner for PDF accessibility violations"""

    def __init__(self, config: Dict):
        self.config = config
        self.results = []
        self.max_file_size = config.get("max_file_size", 50) * 1024 * 1024  # Convert MB to bytes

        # Check if verapdf is available and should be used
        self.use_verapdf = config.get("use_verapdf", True)
        self.verapdf_available = VeraPDFValidator.is_available() if self.use_verapdf else False
        self.verapdf_profile = config.get("verapdf_profile", "PDFUA-1")

        # Check if OCR detection is available and should be used
        self.detect_scanned = config.get("detect_scanned", True)
        self.ocr_detector = ScannedPDFDetector() if self.detect_scanned else None
        self.ocr_available = self.ocr_detector.is_available() if self.ocr_detector else False

    async def scan_pdf(self, pdf_path: Path, source_url: Optional[str] = None) -> Dict:
        """Scan single PDF for accessibility violations

        Args:
            pdf_path: Path to the PDF file
            source_url: Original URL if downloaded from remote source

        Returns:
            Dict with violations in axe-core compatible format
        """
        violations = []
        passes = 0
        incomplete = 0

        display_source = source_url or f"file://{pdf_path}"

        # Try verapdf first if available and enabled
        if self.verapdf_available:
            try:
                validator = VeraPDFValidator()
                verapdf_result = await validator.validate(
                    pdf_path,
                    profile=self.verapdf_profile,
                    format="json"
                )

                # If verapdf succeeded, return its results enhanced with our metadata
                if "error" not in verapdf_result:
                    # Add PDF metadata
                    with pikepdf.open(pdf_path) as pdf:
                        verapdf_result["pdf_version"] = str(pdf.pdf_version)
                        verapdf_result["total_pages"] = len(pdf.pages)
                        verapdf_result["is_tagged"] = self._is_tagged(pdf_path)

                    return verapdf_result

                # verapdf failed, fall through to Python-based checks
            except Exception as e:
                # verapdf failed, fall through to Python-based checks
                violations.append({
                    "id": "verapdf-failed",
                    "impact": "moderate",
                    "description": f"verapdf validation failed, using basic checks: {str(e)}",
                    "help": "verapdf encountered an error. Results below are from basic Python-based validation.",
                    "helpUrl": "",
                    "tags": ["verapdf", "fallback"],
                    "nodes": [{
                        "html": "verapdf validation",
                        "target": ["verapdf"],
                        "failureSummary": f"Error: {str(e)}"
                    }]
                })

        # Check for scanned PDF (image-only) if OCR detection is available
        if self.ocr_available and self.ocr_detector:
            try:
                scanned_violation = self.ocr_detector.get_violation_if_scanned(pdf_path)
                if scanned_violation:
                    violations.append(scanned_violation)
            except Exception as e:
                # OCR detection failed, continue with other checks
                pass

        # Use Python-based checks (either as fallback or primary method)
        try:
            # Open PDF with pikepdf for structure analysis
            with pikepdf.open(pdf_path) as pdf:
                # Basic metadata
                pdf_info = {
                    "pdf_version": str(pdf.pdf_version),
                    "num_pages": len(pdf.pages),
                    "is_encrypted": pdf.is_encrypted,
                }

                # Run all checks
                violations.extend(self._check_tagged_structure(pdf))
                violations.extend(self._check_document_language(pdf))
                violations.extend(self._check_document_title(pdf))

            # Re-open with pikepdf for structure tree analysis
            with pikepdf.open(pdf_path) as pdf:
                violations.extend(self._check_form_accessibility(pdf))
                violations.extend(self._check_bookmarks(pdf))
                violations.extend(self._check_table_structure_tree(pdf))
                violations.extend(self._check_heading_structure(pdf))
                violations.extend(self._check_image_alt_text_structure(pdf))

            # Open with pdfplumber for content analysis (if needed)
            with pdfplumber.open(pdf_path) as pdf:
                violations.extend(self._check_reading_order(pdf))

            # Count passes and incomplete
            passes = self._count_passes(pdf_info)

            return {
                "url": display_source,
                "file_name": pdf_path.name,
                "pdf_version": pdf_info["pdf_version"],
                "total_pages": pdf_info["num_pages"],
                "is_tagged": self._is_tagged(pdf_path),
                "violations": violations,
                "passes": passes,
                "incomplete": incomplete,
            }

        except Exception as e:
            return {
                "url": display_source,
                "file_name": pdf_path.name,
                "error": str(e),
                "violations": [{
                    "id": "pdf-scan-error",
                    "impact": "critical",
                    "description": f"Failed to scan PDF: {str(e)}",
                    "help": "Ensure the PDF is not corrupted and is accessible",
                    "helpUrl": "",
                    "tags": ["pdf-ua"],
                    "nodes": [{
                        "html": "PDF file",
                        "target": [str(pdf_path)],
                        "failureSummary": str(e)
                    }]
                }]
            }

    async def scan(
        self,
        pdf_sources: List[Dict],
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> List[Dict]:
        """Scan multiple PDFs with optional progress callback

        Args:
            pdf_sources: List of dicts with 'path' or 'url' keys
            progress_callback: Optional callback(current, total)

        Returns:
            List of scan results
        """
        results = []
        total = len(pdf_sources)

        for idx, source in enumerate(pdf_sources):
            pdf_path = None
            temp_file = None

            try:
                # Handle URL download
                if "url" in source:
                    pdf_path, temp_file = await self._download_pdf(source["url"])
                    source_url = source["url"]
                else:
                    pdf_path = Path(source["path"])
                    source_url = None

                # Scan the PDF
                result = await self.scan_pdf(pdf_path, source_url)
                results.append(result)

            except Exception as e:
                results.append({
                    "url": source.get("url") or source.get("path"),
                    "error": str(e),
                    "violations": []
                })
            finally:
                # Cleanup temp file
                if temp_file:
                    try:
                        temp_file.unlink()
                    except:
                        pass

            # Report progress
            if progress_callback:
                progress_callback(idx + 1, total)

        return results

    async def _download_pdf(self, url: str) -> tuple[Path, Path]:
        """Download PDF from URL to temporary file

        Returns:
            Tuple of (pdf_path, temp_file_path) for cleanup
        """
        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            response = await client.get(url)
            response.raise_for_status()

            # Check file size
            content_length = response.headers.get("content-length")
            if content_length and int(content_length) > self.max_file_size:
                raise ValueError(
                    f"PDF too large: {int(content_length) / 1024 / 1024:.1f}MB "
                    f"(max: {self.max_file_size / 1024 / 1024:.1f}MB)"
                )

            # Create temp file
            temp_file = Path(tempfile.mktemp(suffix=".pdf"))
            temp_file.write_bytes(response.content)

            return temp_file, temp_file

    def _is_tagged(self, pdf_path: Path) -> bool:
        """Check if PDF has tagged structure"""
        try:
            with pikepdf.open(pdf_path) as pdf:
                # Check for StructTreeRoot in document catalog
                if hasattr(pdf.Root, "StructTreeRoot"):
                    return True
                # Check MarkInfo
                if hasattr(pdf.Root, "MarkInfo"):
                    mark_info = pdf.Root.MarkInfo
                    if hasattr(mark_info, "Marked") and mark_info.Marked:
                        return True
                return False
        except:
            return False

    def _check_tagged_structure(self, pdf: pikepdf.Pdf) -> List[Dict]:
        """Check if PDF has proper tagged structure for accessibility"""
        violations = []

        # Check for StructTreeRoot
        has_structure = hasattr(pdf.Root, "StructTreeRoot")

        # Check MarkInfo
        is_marked = False
        mark_info_exists = hasattr(pdf.Root, "MarkInfo")
        if mark_info_exists:
            mark_info = pdf.Root.MarkInfo
            is_marked = hasattr(mark_info, "Marked") and mark_info.Marked

        if not has_structure or not is_marked:
            # Build detailed failure summary
            issues = []
            if not has_structure:
                issues.append("Missing /Root/StructTreeRoot (structure tree)")
            if not mark_info_exists:
                issues.append("Missing /Root/MarkInfo dictionary")
            elif not is_marked:
                issues.append("/Root/MarkInfo/Marked is false or missing")

            violations.append({
                "id": "pdf-not-tagged",
                "impact": "critical",
                "description": "PDF is not properly tagged for accessibility - screen readers cannot navigate document structure",
                "help": f"""This PDF lacks required tagging for accessibility. Issues found: {', '.join(issues)}

HOW TO FIX:
1. If using Microsoft Word/LibreOffice:
   - Go to File > Export as PDF
   - Check "Create tagged PDF" or "Universal Accessibility (PDF/UA)" option
   - Ensure document uses proper heading styles (Heading 1, Heading 2, etc.)

2. If using Adobe Acrobat Pro:
   - Open PDF in Acrobat Pro
   - Choose Tools > Accessibility > Add Tags to Document
   - Run Tools > Accessibility > Full Check to verify
   - Fix any issues reported

3. For InDesign/other authoring tools:
   - Enable accessibility/tagged PDF export in export settings
   - Use proper semantic styles (headings, lists, tables)
   - Set reading order in layout

WHAT THIS FIXES: Allows screen readers to understand document structure, headings, lists, tables, and reading order.""",
                "helpUrl": "https://www.w3.org/WAI/WCAG21/Techniques/pdf/PDF6",
                "tags": ["pdf-ua", "wcag2a", "wcag412"],
                "nodes": [{
                    "html": f"Document Catalog: {', '.join(issues)}",
                    "target": ["/Root"],
                    "failureSummary": f"Required accessibility properties missing: {'; '.join(issues)}. This prevents assistive technology from understanding document structure."
                }]
            })

        return violations

    def _check_document_language(self, pdf: pikepdf.Pdf) -> List[Dict]:
        """Check if document language is specified"""
        violations = []

        # Check for Lang entry in document catalog
        has_lang = hasattr(pdf.Root, "Lang")
        lang_value = str(pdf.Root.Lang) if has_lang else None

        if not has_lang:
            violations.append({
                "id": "pdf-missing-lang",
                "impact": "serious",
                "description": "PDF document language not specified - screen readers cannot select correct pronunciation rules",
                "help": """The document language (e.g., 'en-US', 'es', 'fr') is not set in the PDF metadata. This causes screen readers to use incorrect pronunciation and voice synthesis.

HOW TO FIX:
1. Using Adobe Acrobat Pro:
   - File > Properties > Advanced tab
   - Set "Language" dropdown to your document's language
   - Click OK and save

2. Using Microsoft Word before PDF export:
   - Review > Language > Set Proofing Language
   - Select document language (applies to whole document or selected text)
   - Export to PDF with accessibility enabled

3. Using pikepdf (Python):
   ```python
   pdf.Root.Lang = 'en-US'  # or 'es', 'fr', 'de', etc.
   ```

4. Using pdftk or similar tools:
   - Use metadata editing to add: Lang: en-US

LANGUAGE CODES: Use ISO 639-1 codes: en-US (US English), en-GB (British English), es (Spanish), fr (French), de (German), ja (Japanese), zh (Chinese), ar (Arabic), etc.

WHAT THIS FIXES: Ensures screen readers use correct pronunciation, voice, and language-specific rules when reading content.""",
                "helpUrl": "https://www.w3.org/WAI/WCAG21/Techniques/pdf/PDF16",
                "tags": ["pdf-ua", "wcag2a", "wcag412"],
                "nodes": [{
                    "html": "Document Catalog - /Root/Lang property is missing",
                    "target": ["/Root/Lang"],
                    "failureSummary": "The /Lang property is not set in the document catalog (/Root). Found: null. Expected: language code like 'en-US', 'es', 'fr', etc. Without this, screen readers cannot determine which language rules and pronunciation to use."
                }]
            })

        return violations

    def _check_document_title(self, pdf: pikepdf.Pdf) -> List[Dict]:
        """Check if document has a title in metadata"""
        violations = []

        has_title = False
        actual_title = None

        # Check document info
        if pdf.docinfo:
            title = pdf.docinfo.get("/Title")
            if title and str(title).strip():
                has_title = True
                actual_title = str(title).strip()

        # Also check if DisplayDocTitle is set
        display_doc_title = False
        if hasattr(pdf.Root, "ViewerPreferences"):
            viewer_prefs = pdf.Root.ViewerPreferences
            if hasattr(viewer_prefs, "DisplayDocTitle"):
                display_doc_title = viewer_prefs.DisplayDocTitle

        if not has_title:
            violations.append({
                "id": "pdf-missing-title",
                "impact": "serious",
                "description": "PDF document title not specified - users cannot identify document in browser tabs, bookmarks, or screen reader lists",
                "help": """The document title is missing from PDF metadata. This makes it hard for users to identify the document when they have multiple PDFs open, or when browsing their file system with a screen reader.

HOW TO FIX:
1. Using Adobe Acrobat Pro:
   - File > Properties > Description tab
   - Enter a descriptive title in the "Title" field (e.g., "Annual Accessibility Report 2024")
   - Click OK and save

2. Using Microsoft Word before PDF export:
   - File > Info > Properties > Advanced Properties
   - On "Summary" tab, enter document title
   - Export to PDF

3. Using LibreOffice:
   - File > Properties > Description tab
   - Enter title in "Title" field
   - Export to PDF

4. Using pikepdf (Python):
   ```python
   with pikepdf.open('input.pdf') as pdf:
       pdf.docinfo['/Title'] = 'Your Document Title Here'
       pdf.save('output.pdf')
   ```

BEST PRACTICES:
- Use a clear, descriptive title (not just filename)
- Keep it concise but meaningful (e.g., "Q3 2024 Financial Report" not "Report.pdf")
- Avoid special characters that might not display correctly

BONUS: Also set ViewerPreferences/DisplayDocTitle to true so the title shows in the window title bar instead of the filename.

WHAT THIS FIXES: Makes documents identifiable in browser tabs, screen reader document lists, and file managers.""",
                "helpUrl": "https://www.w3.org/WAI/WCAG21/Techniques/pdf/PDF18",
                "tags": ["pdf-ua", "wcag2a", "wcag242"],
                "nodes": [{
                    "html": f"Document Info - /Title property: {actual_title or '(empty)'}, DisplayDocTitle: {display_doc_title}",
                    "target": ["/Info/Title"],
                    "failureSummary": f"The /Title property in document info (/Info/Title) is missing or empty. Found: {actual_title or 'null'}. Expected: descriptive title string. Additionally, /Root/ViewerPreferences/DisplayDocTitle should be true to show title instead of filename in window title bar."
                }]
            })

        return violations

    def _check_image_alt_text_structure(self, pdf: pikepdf.Pdf) -> List[Dict]:
        """Check if images have alternative text by analyzing structure tree"""
        violations = []

        # Check if PDF is tagged first
        if not (hasattr(pdf.Root, "StructTreeRoot")):
            # Already caught by tagged structure check
            return violations

        try:
            struct_tree = pdf.Root.StructTreeRoot
            figures_found = []
            figures_without_alt = []
            figures_with_bad_alt = []

            # Recursively find all Figure elements
            def find_figures(element, depth=0):
                if element is None:
                    return

                elem_type = str(element.get("/S", "")) if hasattr(element, 'get') else ""

                if elem_type == "/Figure":
                    # Found a figure, check for alt text
                    has_alt = hasattr(element, "/Alt") or (hasattr(element, 'get') and element.get("/Alt") is not None)
                    alt_text = str(element.get("/Alt", "")) if hasattr(element, 'get') else ""

                    figure_info = {
                        'has_alt': has_alt,
                        'alt_text': alt_text.strip(),
                        'index': len(figures_found) + 1
                    }

                    figures_found.append(figure_info)

                    # Check if alt text is missing or bad
                    if not has_alt or not alt_text.strip():
                        figures_without_alt.append(figure_info)
                    elif is_generic_alt_text(alt_text.strip()):
                        figures_with_bad_alt.append(figure_info)

                # Recurse through children
                if hasattr(element, 'get'):
                    kids = element.get("/K", [])
                    if kids:
                        if not isinstance(kids, list):
                            kids = [kids]
                        for child in kids:
                            find_figures(child, depth + 1)

            # Start recursive search
            find_figures(struct_tree)

            # Report violations for missing alt text
            if figures_without_alt:
                missing_list = ", ".join([f"Figure {f['index']}" for f in figures_without_alt[:10]])
                if len(figures_without_alt) > 10:
                    missing_list += f"... and {len(figures_without_alt) - 10} more"

                violations.append({
                    "id": "pdf-images-missing-alt",
                    "impact": "serious",
                    "description": f"{len(figures_without_alt)} of {len(figures_found)} images lack alternative text - completely inaccessible to screen readers",
                    "help": f"""Found {len(figures_without_alt)} images without alt text out of {len(figures_found)} total images in PDF.

IMAGES WITHOUT ALT TEXT: {missing_list}

WHY THIS IS SERIOUS:
Images without alt text are completely invisible to screen reader users. The user has no idea what visual information they're missing.

HOW TO FIX:
1. Using Adobe Acrobat Pro:
   - Tools > Accessibility > Reading Order
   - Find each image marked as <Figure>
   - Right-click > Edit Alternate Text
   - Add descriptive text explaining what the image shows
   - For decorative images: check "Decorative figure"

2. Best practices for alt text:
   - Describe the content and function, not just "image"
   - Good: "Line graph showing revenue growth from 2020 to 2024, increasing from $2M to $5M"
   - Bad: "graph.png" or "image" or "" (empty)
   - Keep it concise but meaningful (aim for 150 characters or less)
   - For complex diagrams: provide detailed description in document body

3. Using pikepdf (Python - for automation):
   ```python
   # Find Figure tags in structure tree and add /Alt property
   figure.Alt = "Description of the image"
   ```

WHAT TO VERIFY:
✓ Every Figure tag has /Alt property
✓ Alt text is descriptive, not generic
✓ Decorative images are marked as Artifact, not Figure

WHAT THIS FIXES: Makes visual information accessible to blind users via screen reader descriptions.""",
                    "helpUrl": "https://www.w3.org/WAI/WCAG21/Techniques/pdf/PDF1",
                    "tags": ["pdf-ua", "wcag2a", "wcag111"],
                    "nodes": [{
                        "html": f"{len(figures_without_alt)} images without alt text: {missing_list}",
                        "target": ["//Figure"],
                        "failureSummary": f"Structure tree contains {len(figures_found)} Figure tags. {len(figures_without_alt)} have missing or empty /Alt property. Screen readers cannot describe these images to blind users. Each Figure tag must have /Alt property with descriptive text."
                    }]
                })

            # Report violations for generic/bad alt text
            if figures_with_bad_alt:
                bad_examples = []
                for f in figures_with_bad_alt[:5]:
                    bad_examples.append(f"Figure {f['index']}: \"{f['alt_text']}\"")

                bad_list = "; ".join(bad_examples)
                if len(figures_with_bad_alt) > 5:
                    bad_list += f"... and {len(figures_with_bad_alt) - 5} more"

                violations.append({
                    "id": "pdf-images-generic-alt",
                    "impact": "moderate",
                    "description": f"{len(figures_with_bad_alt)} images have generic or non-descriptive alternative text",
                    "help": f"""Found {len(figures_with_bad_alt)} images with generic alt text that doesn't meaningfully describe the image.

GENERIC ALT TEXT EXAMPLES: {bad_list}

WHY THIS IS A PROBLEM:
Alt text like "image", "photo", "IMG_1234.jpg", or "figure" tells screen reader users nothing useful. It's nearly as bad as missing alt text entirely.

GENERIC PATTERNS TO AVOID:
- Filenames: "image.jpg", "IMG_1234.png", "photo.gif"
- Generic words: "image", "photo", "picture", "graphic", "figure"
- Just numbers: "1", "2", "figure1"
- Placeholder text: "image description", "alt text", "placeholder"

HOW TO FIX:
Replace generic alt text with actual descriptions:
- Bad: "image.jpg"
  Good: "Screenshot of accessibility settings panel showing keyboard navigation options"
- Bad: "graph"
  Good: "Bar chart comparing website traffic between mobile and desktop users, showing mobile at 65%"
- Bad: "figure1"
  Good: "Workflow diagram illustrating the PDF remediation process from scan to validation"

WHAT MAKES GOOD ALT TEXT:
✓ Describes what the image shows, not that it IS an image
✓ Conveys the same information a sighted user would get
✓ Concise but complete (aim for 1-2 sentences)
✓ Provides context relevant to the document

WHAT THIS FIXES: Ensures screen reader users get meaningful image descriptions, not useless generic text.""",
                    "helpUrl": "https://www.w3.org/WAI/WCAG21/Techniques/pdf/PDF1",
                    "tags": ["pdf-ua", "wcag2a", "wcag111", "quality"],
                    "nodes": [{
                        "html": f"{len(figures_with_bad_alt)} images with generic alt: {bad_list}",
                        "target": ["//Figure"],
                        "failureSummary": f"Found {len(figures_with_bad_alt)} Figure tags with generic alt text that doesn't describe the image. Examples: {bad_list}. Alt text should be descriptive and meaningful, not filenames or generic words."
                    }]
                })

        except Exception as e:
            # Structure tree analysis failed, skip this check
            pass

        return violations

    def _check_heading_hierarchy(self, pdf: pdfplumber.PDF) -> List[Dict]:
        """Check for logical heading hierarchy (placeholder)"""
        # This is complex and requires analyzing structure tree
        # For MVP, we'll add a manual check reminder
        return []

    def _check_reading_order(self, pdf: pdfplumber.PDF) -> List[Dict]:
        """Check reading order logic (placeholder)"""
        # Complex check requiring structure tree analysis
        # For MVP, returning empty list
        return []

    def _check_form_accessibility(self, pdf: pikepdf.Pdf) -> List[Dict]:
        """Check if form fields have proper accessibility attributes"""
        violations = []

        # Check for AcroForm
        if hasattr(pdf.Root, "AcroForm"):
            acro_form = pdf.Root.AcroForm
            if hasattr(acro_form, "Fields"):
                fields = acro_form.Fields
                unlabeled_fields = []
                field_details = []

                # Check each form field for accessibility
                for idx, field in enumerate(fields):
                    # Check for TU (tooltip/alternative description)
                    has_tu = hasattr(field, "TU") and str(field.TU).strip()
                    # Check for T (field name)
                    has_name = hasattr(field, "T") and str(field.T).strip()

                    # Get field type if available
                    field_type = str(field.FT) if hasattr(field, "FT") else "Unknown"

                    if not has_tu and not has_name:
                        unlabeled_fields.append(idx + 1)
                        field_details.append(f"Field {idx + 1} (Type: {field_type})")

                if unlabeled_fields:
                    total_fields = len(fields)
                    field_list = ", ".join(field_details[:10])
                    if len(field_details) > 10:
                        field_list += f"... and {len(field_details) - 10} more"

                    violations.append({
                        "id": "pdf-form-fields-unlabeled",
                        "impact": "serious",
                        "description": f"{len(unlabeled_fields)} of {total_fields} form fields lack proper labels or tooltips - screen reader users cannot identify field purpose",
                        "help": f"""Form fields must have labels so screen reader users know what information to enter. This PDF has {len(unlabeled_fields)} unlabeled fields.

AFFECTED FIELDS: {field_list}

HOW TO FIX:
1. Using Adobe Acrobat Pro:
   - Tools > Prepare Form
   - Right-click each form field > Properties
   - On "General" tab, fill in "Name" field (internal identifier)
   - On "Options" tab (or "General" tab), fill in "Tooltip" field (what screen reader announces)
   - Tooltip should describe what user should enter: e.g., "First Name", "Email Address", "Date of Birth (MM/DD/YYYY)"

2. Best practices for form field labels:
   - Tooltip text (/TU) is what screen readers announce - make it clear and descriptive
   - Field name (/T) should be unique and meaningful
   - Good tooltip: "Email Address" or "Street Address Line 1"
   - Bad tooltip: "Text1" or "" (empty)
   - Include format hints: "Phone Number (10 digits, no spaces)"

3. For checkboxes and radio buttons:
   - Each option needs a descriptive label
   - Group related options together
   - Example: "Preferred contact method: Email" not just "Email"

4. Using pikepdf (Python - for automation):
   ```python
   for field in pdf.Root.AcroForm.Fields:
       field.TU = "Descriptive label here"  # Set tooltip
       field.T = "unique_field_name"        # Set field name
   ```

WHAT TO VERIFY:
✓ Every field has a tooltip (/TU property)
✓ Tooltips are descriptive and unique
✓ Format requirements are explained (e.g., date format)
✓ Required vs. optional is indicated

WHAT THIS FIXES: Screen reader users can understand what information each field requires and fill out forms independently.""",
                        "helpUrl": "https://www.w3.org/WAI/WCAG21/Techniques/pdf/PDF5",
                        "tags": ["pdf-ua", "wcag2a", "wcag412"],
                        "nodes": [{
                            "html": f"Form contains {total_fields} fields, {len(unlabeled_fields)} unlabeled: {field_list}",
                            "target": ["/AcroForm/Fields"],
                            "failureSummary": f"Found {len(unlabeled_fields)} form fields without both /TU (tooltip) and /T (name) properties. Fields: {', '.join([str(f) for f in unlabeled_fields[:10]])}{'...' if len(unlabeled_fields) > 10 else ''}. Each field must have at minimum a /TU property containing descriptive label text that screen readers will announce."
                        }]
                    })

        return violations

    def _check_table_structure(self, pdf: pdfplumber.PDF) -> List[Dict]:
        """Check for proper table structure"""
        violations = []

        # Count tables across all pages
        total_tables = 0
        tables_by_page = []
        for idx, page in enumerate(pdf.pages, 1):
            tables = page.find_tables()
            if len(tables) > 0:
                total_tables += len(tables)
                # Get table dimensions
                table_info = []
                for table in tables:
                    rows = len(table.rows) if hasattr(table, 'rows') else 'unknown'
                    cols = len(table.bbox) if hasattr(table, 'bbox') else 'unknown'
                    table_info.append(f"{rows}×{cols}")
                tables_by_page.append(f"Page {idx}: {len(tables)} table(s) [{', '.join(table_info)}]")

        if total_tables > 0:
            page_list = "; ".join(tables_by_page[:5])
            if len(tables_by_page) > 5:
                page_list += f"... and {len(tables_by_page) - 5} more pages"

            violations.append({
                "id": "pdf-tables-need-review",
                "impact": "moderate",
                "description": f"PDF contains {total_tables} tables across {len(tables_by_page)} pages - all tables must be manually verified for proper structure and headers",
                "help": f"""This PDF contains {total_tables} data tables. Each table must be properly tagged with headers so screen reader users can navigate and understand the data relationships.

TABLES FOUND: {page_list}

HOW TO CHECK & FIX:
1. Using Adobe Acrobat Pro:
   - Tools > Accessibility > Reading Order
   - Check that each table is tagged as <Table> in structure tree
   - Right-click table > Table Editor
   - Verify first row is marked as headers (TH tags)
   - Verify data cells are marked as TD tags
   - Check for merged cells - they need proper span attributes

2. Table structure requirements:
   - Entire table must be wrapped in <Table> tag
   - Header row(s) must use <TH> (table header) tags
   - Data cells must use <TD> (table data) tags
   - Column headers should have scope="col" attribute
   - Row headers should have scope="row" attribute
   - Merged cells need proper rowspan/colspan attributes

3. Best practices:
   - Simple tables work best (avoid complex nested tables)
   - Use actual table tags, not just grid lines or tabs
   - Every column should have a clear header
   - Avoid blank cells if possible - use "N/A" or "-"
   - For multi-level headers, properly associate headers with data cells

4. Manual verification checklist:
   ✓ Table tagged in structure tree
   ✓ Headers in first row/column marked as TH
   ✓ Data cells marked as TD
   ✓ Headers associated with correct cells
   ✓ Table has summary/caption if complex
   ✓ Reading order flows logically

WHAT TO TEST:
- Navigate table with screen reader (NVDA/JAWS/VoiceOver)
- Check that headers are announced with each data cell
- Verify you can navigate by row/column
- Ensure table summary is read if present

WHAT THIS FIXES: Screen reader users can understand data relationships, navigate tables efficiently, and comprehend which headers apply to each data cell.""",
                "helpUrl": "https://www.w3.org/WAI/WCAG21/Techniques/pdf/PDF6",
                "tags": ["pdf-ua", "wcag2a", "wcag131", "needs-manual-review"],
                "nodes": [{
                    "html": f"{total_tables} tables detected: {page_list}",
                    "target": ["//Table"],
                    "failureSummary": f"Found {total_tables} table structures in document. Automated tools cannot verify: (1) if tables are properly tagged as <Table> in structure tree, (2) if header cells use <TH> tags with scope attributes, (3) if data cells use <TD> tags, (4) if merged cells have proper rowspan/colspan. Manual review required using Adobe Acrobat Pro > Tools > Accessibility > Reading Order."
                }]
            })

        return violations

    def _check_bookmarks(self, pdf: pikepdf.Pdf) -> List[Dict]:
        """Check if document has bookmarks/table of contents"""
        violations = []

        # Check for Outlines (bookmarks/TOC)
        has_outlines = hasattr(pdf.Root, "Outlines")

        # Only flag as violation if document is long enough to benefit from bookmarks
        num_pages = len(pdf.pages)
        if not has_outlines and num_pages > 10:
            # Provide different recommendations based on page count
            severity = "moderate" if num_pages < 50 else "serious"
            page_description = f"{num_pages} pages"
            if num_pages > 100:
                page_description = f"{num_pages} pages (very long document)"
            elif num_pages > 50:
                page_description = f"{num_pages} pages (long document)"

            violations.append({
                "id": "pdf-missing-bookmarks",
                "impact": severity,
                "description": f"PDF has {page_description} but no bookmarks/table of contents - users cannot quickly navigate to sections",
                "help": f"""This {page_description} PDF lacks bookmarks (also called outlines or table of contents). Bookmarks provide critical navigation for all users, especially those using screen readers or keyboard navigation.

DOCUMENT SIZE: {num_pages} pages - bookmarks are {'essential' if num_pages > 50 else 'recommended'}

HOW TO FIX:
1. Using Microsoft Word before PDF export:
   - Use heading styles (Heading 1, Heading 2, etc.) throughout document
   - File > Export > Create PDF/XPS
   - Click "Options" button
   - Check "Create bookmarks using: Headings"
   - Click OK and export
   - Bookmarks automatically generated from headings

2. Using Adobe Acrobat Pro:
   - Tools > Organize Pages > Bookmarks > Add from Structure
   - Or manually: Tools > Edit PDF > More > Add Bookmark
   - Create hierarchical structure matching document sections
   - Name bookmarks clearly (e.g., "Chapter 1: Introduction" not "Bookmark1")

3. Using LibreOffice Writer:
   - Use heading paragraph styles throughout document
   - File > Export as PDF
   - On "General" tab, check "Export bookmarks"
   - Bookmarks generated automatically from headings

4. Using InDesign:
   - Create TOC using Table of Contents feature
   - File > Export > Adobe PDF (Print)
   - On "General" tab, enable "Bookmarks"
   - Bookmarks match TOC structure

5. Using pikepdf (Python - for automation):
   ```python
   # Add bookmarks programmatically
   with pikepdf.open('input.pdf') as pdf:
       outline = pdf.make_indirect(pikepdf.Dictionary(Type='/Outlines'))
       pdf.Root.Outlines = outline
       # Add bookmark items...
   ```

BEST PRACTICES:
- Match bookmark hierarchy to document structure (chapters, sections, subsections)
- Use clear, descriptive names
- Don't go too deep (2-3 levels usually sufficient)
- Include major sections, skip minor subsections
- Test navigation - can you jump to any section easily?

RECOMMENDED STRUCTURE for a {num_pages}-page document:
{self._get_bookmark_recommendation(num_pages)}

WHAT TO TEST:
- Open bookmarks panel (usually on left side of PDF viewer)
- Click each bookmark - does it jump to the right section?
- Is hierarchy logical and easy to follow?
- Are bookmark names descriptive?

WHAT THIS FIXES: Provides quick navigation to any section, reduces scrolling, helps users understand document structure, makes long documents accessible.""",
                "helpUrl": "https://www.w3.org/WAI/WCAG21/Techniques/pdf/PDF2",
                "tags": ["pdf-ua", "wcag2a", "wcag241"],
                "nodes": [{
                    "html": f"Document: {num_pages} pages, no navigation structure",
                    "target": ["/Root/Outlines"],
                    "failureSummary": f"The /Outlines entry is missing from document catalog (/Root/Outlines). This {num_pages}-page document has no bookmark/outline structure for navigation. Users must scroll page-by-page or search to find content. For documents over 10 pages, bookmarks are essential for accessibility and usability. Add bookmarks matching document's heading hierarchy."
                }]
            })

        return violations

    def _check_table_structure_tree(self, pdf: pikepdf.Pdf) -> List[Dict]:
        """Check table structure by analyzing PDF structure tree"""
        violations = []

        # Check if PDF is tagged first
        if not (hasattr(pdf.Root, "StructTreeRoot")):
            # Already caught by tagged structure check
            return violations

        try:
            struct_tree = pdf.Root.StructTreeRoot
            tables_found = []
            tables_with_issues = []

            # Recursively find all Table elements in structure tree
            def find_tables(element, path=""):
                if element is None:
                    return

                # Get element type
                elem_type = str(element.get("/S", "")) if hasattr(element, 'get') else ""

                if elem_type == "/Table":
                    # Found a table, check its structure
                    table_info = self._analyze_table_element(element, path)
                    tables_found.append(table_info)
                    if table_info.get('has_issues'):
                        tables_with_issues.append(table_info)

                # Recurse through children
                if hasattr(element, 'get'):
                    kids = element.get("/K", [])
                    if kids:
                        # K can be a single item or array
                        if not isinstance(kids, list):
                            kids = [kids]
                        for idx, child in enumerate(kids):
                            find_tables(child, f"{path}/{elem_type}[{idx}]")

            # Start recursive search
            find_tables(struct_tree)

            # Report violations if tables have issues
            if tables_with_issues:
                issues_summary = []
                for table in tables_with_issues[:5]:
                    issue_desc = ", ".join(table.get('issues', []))
                    issues_summary.append(f"Table {table.get('index', '?')}: {issue_desc}")

                violations.append({
                    "id": "pdf-table-structure-invalid",
                    "impact": "serious",
                    "description": f"{len(tables_with_issues)} of {len(tables_found)} tables have structural accessibility issues",
                    "help": f"""Found {len(tables_found)} tables in PDF structure tree, but {len(tables_with_issues)} have accessibility problems:

ISSUES FOUND:
{chr(10).join(f"- {issue}" for issue in issues_summary[:5])}
{f"... and {len(tables_with_issues) - 5} more tables with issues" if len(tables_with_issues) > 5 else ""}

HOW TO FIX:
1. Using Adobe Acrobat Pro:
   - Tools > Accessibility > Reading Order
   - Find each problematic table
   - Right-click table > Table Editor
   - Ensure first row cells are marked as headers (TH)
   - Ensure data cells are marked as TD
   - Add scope attributes (scope="col" for column headers, scope="row" for row headers)

2. Common table structure issues:
   - **Missing header cells**: First row must use <TH> tags, not <TD>
   - **No scope attributes**: Headers need scope="col" or scope="row"
   - **Irregular structure**: All rows must have same number of cells
   - **Missing table wrapper**: Content must be inside <Table> tag

3. Proper table structure:
   ```
   <Table>
     <TR>
       <TH scope="col">Header 1</TH>
       <TH scope="col">Header 2</TH>
     </TR>
     <TR>
       <TD>Data 1</TD>
       <TD>Data 2</TD>
     </TR>
   </Table>
   ```

WHAT TO FIX:
{chr(10).join(f"✗ {issue}" for issue in issues_summary)}

WHAT THIS FIXES: Screen readers can identify table headers, navigate by row/column, and understand data relationships.""",
                    "helpUrl": "https://www.w3.org/WAI/WCAG21/Techniques/pdf/PDF6",
                    "tags": ["pdf-ua", "wcag2a", "wcag131"],
                    "nodes": [{
                        "html": f"{len(tables_with_issues)} tables with issues out of {len(tables_found)} total",
                        "target": ["//Table"],
                        "failureSummary": f"Structure tree analysis found {len(tables_with_issues)} tables with accessibility issues. Common problems: missing TH (table header) tags, using TD for headers, missing scope attributes, irregular row structure. Each table must have proper header markup for screen reader navigation."
                    }]
                })

        except Exception as e:
            # Structure tree analysis failed, fall back to detection-only approach
            pass

        return violations

    def _analyze_table_element(self, table_elem, path: str) -> Dict:
        """Analyze a single table element for accessibility issues"""
        issues = []
        has_th = False
        has_td = False
        row_count = 0

        def check_children(element):
            nonlocal has_th, has_td, row_count

            if element is None:
                return

            elem_type = str(element.get("/S", "")) if hasattr(element, 'get') else ""

            if elem_type == "/TH":
                has_th = True
            elif elem_type == "/TD":
                has_td = True
            elif elem_type == "/TR":
                row_count += 1

            # Recurse
            if hasattr(element, 'get'):
                kids = element.get("/K", [])
                if kids:
                    if not isinstance(kids, list):
                        kids = [kids]
                    for child in kids:
                        check_children(child)

        check_children(table_elem)

        # Identify issues
        if not has_th:
            issues.append("No header cells (TH) found")
        if row_count == 0:
            issues.append("No table rows (TR) found")
        if has_td and not has_th:
            issues.append("Uses TD for all cells (headers should be TH)")

        return {
            'path': path,
            'has_th': has_th,
            'has_td': has_td,
            'row_count': row_count,
            'issues': issues,
            'has_issues': len(issues) > 0,
            'index': len(issues)  # Placeholder for table index
        }

    def _check_heading_structure(self, pdf: pikepdf.Pdf) -> List[Dict]:
        """Check heading hierarchy by analyzing structure tree"""
        violations = []

        # Check if PDF is tagged first
        if not (hasattr(pdf.Root, "StructTreeRoot")):
            return violations

        try:
            struct_tree = pdf.Root.StructTreeRoot
            headings_found = []
            hierarchy_issues = []

            # Recursively find all heading elements
            def find_headings(element, depth=0):
                if element is None:
                    return

                elem_type = str(element.get("/S", "")) if hasattr(element, 'get') else ""

                # Check for heading tags (H1-H6, H)
                if elem_type in ["/H1", "/H2", "/H3", "/H4", "/H5", "/H6", "/H"]:
                    level = int(elem_type[2]) if elem_type != "/H" else 0
                    headings_found.append({'type': elem_type, 'level': level, 'depth': depth})

                # Recurse
                if hasattr(element, 'get'):
                    kids = element.get("/K", [])
                    if kids:
                        if not isinstance(kids, list):
                            kids = [kids]
                        for child in kids:
                            find_headings(child, depth + 1)

            find_headings(struct_tree)

            # Analyze hierarchy
            if len(headings_found) > 1:
                prev_level = 0
                for idx, heading in enumerate(headings_found):
                    level = heading['level']
                    if level == 0:  # Generic /H tag
                        continue

                    # Check for skipped levels
                    if prev_level > 0 and level > prev_level + 1:
                        hierarchy_issues.append(f"Heading {idx + 1}: Skips from H{prev_level} to H{level}")

                    prev_level = level

            if hierarchy_issues:
                violations.append({
                    "id": "pdf-heading-hierarchy-invalid",
                    "impact": "moderate",
                    "description": f"Document has {len(hierarchy_issues)} heading hierarchy violations",
                    "help": f"""Heading hierarchy issues found:

ISSUES:
{chr(10).join(f"- {issue}" for issue in hierarchy_issues[:10])}

HOW TO FIX: Headings must follow logical order (H1 → H2 → H3), not skip levels (H1 → H3 ✗). Use authoring tool's heading styles properly.""",
                    "helpUrl": "https://www.w3.org/WAI/WCAG21/Techniques/pdf/PDF9",
                    "tags": ["pdf-ua", "wcag2a", "wcag131"],
                    "nodes": [{
                        "html": f"{len(headings_found)} headings found, {len(hierarchy_issues)} hierarchy issues",
                        "target": ["//H1", "//H2", "//H3"],
                        "failureSummary": f"Found {len(hierarchy_issues)} heading hierarchy violations. {'; '.join(hierarchy_issues[:3])}"
                    }]
                })

        except Exception:
            # Structure tree analysis failed
            pass

        return violations

    def _get_bookmark_recommendation(self, num_pages: int) -> str:
        """Get bookmark structure recommendation based on page count"""
        if num_pages < 20:
            return "- 1 bookmark per major section (3-5 bookmarks total)"
        elif num_pages < 50:
            return "- Level 1: Chapters/major sections\n- Level 2: Subsections within chapters\n- Aim for 5-10 top-level bookmarks"
        elif num_pages < 100:
            return "- Level 1: Chapters (10-15 bookmarks)\n- Level 2: Sections within chapters\n- Level 3: Major subsections if needed"
        else:
            return "- Level 1: Parts or major divisions\n- Level 2: Chapters\n- Level 3: Sections\n- Consider adding bookmark to executive summary, table of contents, index"

    def _count_passes(self, pdf_info: Dict) -> int:
        """Count number of passed checks"""
        # Simple heuristic for now
        return 0

    def _create_violation(
        self,
        violation_id: str,
        impact: str,
        description: str,
        help_text: str,
        help_url: str,
        tags: List[str],
        target: str,
        failure_summary: str
    ) -> Dict:
        """Create a violation dict in axe-core format"""
        return {
            "id": violation_id,
            "impact": impact,
            "description": description,
            "help": help_text,
            "helpUrl": help_url,
            "tags": tags,
            "nodes": [{
                "html": "PDF element",
                "target": [target],
                "failureSummary": failure_summary
            }]
        }
