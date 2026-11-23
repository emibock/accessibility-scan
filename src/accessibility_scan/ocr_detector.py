"""OCR-based detection for scanned (image-only) PDFs

Scanned PDFs are images without a text layer - fundamentally inaccessible to screen readers.
This module detects them by comparing embedded text vs OCR-extracted text.
"""

import re
from pathlib import Path
from typing import Dict, Tuple
from io import BytesIO

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import pytesseract
    PYTESSERACT_AVAILABLE = True
except ImportError:
    PYTESSERACT_AVAILABLE = False

import pdfplumber


class OCRDetector:
    """Detect scanned (image-only) PDFs using OCR analysis"""

    @staticmethod
    def is_available() -> bool:
        """Check if OCR detection is available (requires PIL and pytesseract)"""
        return PIL_AVAILABLE and PYTESSERACT_AVAILABLE

    @staticmethod
    def check_tesseract_installed() -> bool:
        """Check if tesseract binary is actually installed"""
        if not PYTESSERACT_AVAILABLE:
            return False

        try:
            pytesseract.get_tesseract_version()
            return True
        except Exception:
            return False

    def detect_scanned_pdf(
        self,
        pdf_path: Path,
        sample_pages: int = 3,
        text_threshold: float = 0.1
    ) -> Dict:
        """Detect if PDF is scanned by comparing embedded text vs OCR text

        Args:
            pdf_path: Path to PDF file
            sample_pages: Number of pages to sample (default: 3, checks first/middle/last)
            text_threshold: Ratio threshold (embedded/OCR text) below which PDF is considered scanned

        Returns:
            Dict with detection results:
            {
                "is_scanned": bool,
                "confidence": float (0-1),
                "embedded_text_length": int,
                "ocr_text_length": int,
                "ratio": float,
                "pages_sampled": int,
                "method": str
            }
        """
        if not self.is_available():
            return {
                "is_scanned": False,
                "confidence": 0.0,
                "error": "OCR detection not available (requires Pillow and pytesseract)",
                "method": "unavailable"
            }

        if not self.check_tesseract_installed():
            return {
                "is_scanned": False,
                "confidence": 0.0,
                "error": "Tesseract OCR not installed",
                "method": "unavailable"
            }

        try:
            with pdfplumber.open(pdf_path) as pdf:
                total_pages = len(pdf.pages)

                # Determine which pages to sample
                if total_pages <= sample_pages:
                    page_indices = list(range(total_pages))
                else:
                    # Sample: first, middle, last pages
                    page_indices = [
                        0,  # First page
                        total_pages // 2,  # Middle page
                        total_pages - 1  # Last page
                    ][:sample_pages]

                total_embedded_text = 0
                total_ocr_text = 0
                pages_checked = 0

                for page_idx in page_indices:
                    try:
                        page = pdf.pages[page_idx]

                        # Extract embedded text
                        embedded_text = page.extract_text() or ""
                        embedded_chars = len(self._clean_text(embedded_text))

                        # Extract via OCR
                        ocr_text = self._ocr_page(page)
                        ocr_chars = len(self._clean_text(ocr_text))

                        total_embedded_text += embedded_chars
                        total_ocr_text += ocr_chars
                        pages_checked += 1

                    except Exception as e:
                        # Skip pages that fail to process
                        continue

                if pages_checked == 0:
                    return {
                        "is_scanned": False,
                        "confidence": 0.0,
                        "error": "Failed to process any pages",
                        "method": "error"
                    }

                # Calculate ratio of embedded to OCR text
                if total_ocr_text == 0:
                    # No text found by OCR - probably blank pages or already has text
                    ratio = 1.0 if total_embedded_text > 0 else 0.0
                else:
                    ratio = total_embedded_text / total_ocr_text

                # Determine if scanned
                # - If ratio < threshold and OCR found significant text → scanned
                # - If OCR found very little text → not conclusive
                is_scanned = (ratio < text_threshold) and (total_ocr_text > 100)

                # Calculate confidence
                # High confidence if:
                # - OCR found lots of text (>500 chars) but embedded text is minimal
                # - Or embedded text is very close to OCR (not scanned)
                if is_scanned:
                    # Confidence based on how much text OCR found vs embedded
                    confidence = min(1.0, (total_ocr_text - total_embedded_text) / 1000)
                else:
                    # Confidence based on how much embedded text exists
                    if total_embedded_text > 500:
                        confidence = 0.9  # Definitely has text layer
                    elif total_ocr_text > 0:
                        confidence = ratio  # Proportional to embedded/OCR ratio
                    else:
                        confidence = 0.0  # No text detected anywhere

                return {
                    "is_scanned": is_scanned,
                    "confidence": round(confidence, 2),
                    "embedded_text_length": total_embedded_text,
                    "ocr_text_length": total_ocr_text,
                    "ratio": round(ratio, 2),
                    "pages_sampled": pages_checked,
                    "total_pages": total_pages,
                    "method": "ocr_comparison"
                }

        except Exception as e:
            return {
                "is_scanned": False,
                "confidence": 0.0,
                "error": str(e),
                "method": "error"
            }

    def _ocr_page(self, page) -> str:
        """Run OCR on a PDF page

        Args:
            page: pdfplumber Page object

        Returns:
            Extracted text from OCR
        """
        try:
            # Convert page to image
            # pdfplumber can render pages as PIL images
            img = page.to_image(resolution=150)  # 150 DPI for decent OCR

            # Get the PIL image
            pil_image = img.original

            # Run tesseract OCR
            text = pytesseract.image_to_string(pil_image, lang='eng')

            return text

        except Exception as e:
            return ""

    def _clean_text(self, text: str) -> str:
        """Clean text for comparison (remove whitespace, normalize)"""
        if not text:
            return ""

        # Remove all whitespace
        text = re.sub(r'\s+', '', text)

        # Remove common OCR artifacts
        text = re.sub(r'[^\w\d]', '', text)

        return text


class ScannedPDFDetector:
    """Higher-level detector with simplified API"""

    def __init__(self):
        self.detector = OCRDetector()

    def is_available(self) -> bool:
        """Check if detection is available"""
        return self.detector.is_available()

    def detect(self, pdf_path: Path) -> Tuple[bool, Dict]:
        """Detect if PDF is scanned and return detailed results

        Args:
            pdf_path: Path to PDF file

        Returns:
            Tuple of (is_scanned: bool, details: Dict)
        """
        result = self.detector.detect_scanned_pdf(pdf_path)
        is_scanned = result.get("is_scanned", False)
        return is_scanned, result

    def get_violation_if_scanned(self, pdf_path: Path) -> Dict:
        """Check if PDF is scanned and return a violation dict if it is

        Returns:
            Violation dict if scanned, empty dict otherwise
        """
        is_scanned, details = self.detect(pdf_path)

        if not is_scanned:
            return {}

        # Build detailed failure information
        embedded = details.get("embedded_text_length", 0)
        ocr = details.get("ocr_text_length", 0)
        pages_sampled = details.get("pages_sampled", 0)
        total_pages = details.get("total_pages", 0)
        confidence = details.get("confidence", 0.0)

        return {
            "id": "pdf-scanned-document",
            "impact": "critical",
            "description": f"PDF appears to be a scanned image without a text layer - fundamentally inaccessible to screen readers",
            "help": f"""This PDF is likely a scanned document (image-only) with no accessible text layer.

DETECTION DETAILS:
- Embedded text found: {embedded} characters
- OCR-detected text: {ocr} characters
- Pages sampled: {pages_sampled} of {total_pages}
- Confidence: {confidence * 100:.0f}%

WHY THIS IS CRITICAL:
Scanned PDFs are images, not text. Screen readers cannot read them at all - they appear completely blank to blind users. This is the most severe accessibility barrier in PDFs.

HOW TO FIX:

**Option 1: OCR + Remediation (Recommended)**
1. Using Adobe Acrobat Pro:
   - Tools > Scan & OCR > Recognize Text > In This File
   - Select all pages, choose language
   - Click "Recognize Text"
   - Then run Tools > Accessibility > Add Tags to Document
   - Run full accessibility check and fix issues

2. Using ABBYY FineReader (professional OCR):
   - Open scanned PDF
   - Run OCR with "Create accessible PDF" option
   - Export as tagged PDF/UA compliant PDF
   - More accurate than Acrobat for complex documents

**Option 2: Recreate from Source (Best Quality)**
If you have the original source document:
1. Locate the original Word/Excel/InDesign file
2. Create a new PDF using the authoring tool's accessibility features
3. This produces much better results than OCR

**Option 3: Retype/Recreate (Last Resort)**
For short documents:
1. Create a new document from scratch
2. Type the content with proper structure
3. Export as accessible PDF

**Prevention:**
- Never scan to PDF if you have the original document
- If scanning is necessary:
  - Use high resolution (300+ DPI)
  - Apply OCR immediately after scanning
  - Verify text is selectable before distributing

**Testing:**
After fixing, verify by:
1. Opening PDF in reader and trying to select text
2. Using screen reader (NVDA/JAWS) to read content
3. Running this scanner again to confirm issue is resolved

WHAT THIS FIXES: Converts unusable image into readable, accessible text that screen readers can process.""",
            "helpUrl": "https://www.w3.org/WAI/WCAG21/Techniques/pdf/PDF7",
            "tags": ["pdf-ua", "wcag2a", "wcag111", "critical", "scanned"],
            "nodes": [{
                "html": f"Scanned PDF detected: {embedded} chars embedded vs {ocr} chars via OCR (confidence: {confidence * 100:.0f}%)",
                "target": ["document"],
                "failureSummary": f"OCR analysis of {pages_sampled} sample pages found {ocr} characters of text via image recognition, but only {embedded} characters are embedded as actual text. This indicates the PDF is primarily or entirely scanned images. Screen readers can only access embedded text, so this document would appear blank or mostly blank to blind users. Confidence: {confidence * 100:.0f}%."
            }]
        }
