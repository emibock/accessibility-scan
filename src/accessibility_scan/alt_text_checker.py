"""Shared utilities for checking alt text quality

Used by both web and PDF scanners to detect generic/non-descriptive alt text.
"""

import re


def is_generic_alt_text(alt_text: str) -> bool:
    """Check if alt text appears to be generic/non-descriptive

    Args:
        alt_text: The alt text string to check

    Returns:
        True if the alt text appears generic, False if it seems descriptive
    """
    if not alt_text:
        return False

    alt_lower = alt_text.lower().strip()

    # Common generic patterns
    generic_patterns = [
        # Exact matches for generic words
        "image", "photo", "picture", "graphic", "figure", "diagram",
        "chart", "graph", "illustration", "screenshot", "icon",
        # Placeholders
        "alt text", "image description", "placeholder", "todo",
        "alt", "description", "img",
        # Just numbers or single letters
        "1", "2", "3", "4", "5", "6", "7", "8", "9", "0",
        "a", "b", "c", "d", "e",
    ]

    if alt_lower in generic_patterns:
        return True

    # Filename patterns (contains common image extensions)
    image_extensions = [
        '.jpg', '.jpeg', '.png', '.gif', '.svg', '.bmp',
        '.webp', '.tif', '.tiff', '.ico', '.heic', '.heif'
    ]
    if any(ext in alt_lower for ext in image_extensions):
        return True

    # Generic word + number patterns (image1, photo2, figure3, etc.)
    if re.match(r'^(image|photo|picture|figure|img|pic|graphic)\s*\d+$', alt_lower):
        return True

    # Filename-like patterns (IMG_1234, DSC_5678, etc.)
    if re.match(r'^(img|dsc|photo|pic)[-_]\d+', alt_lower):
        return True

    # Very short non-descriptive text (1-3 characters)
    # Exception: Some valid alt text might be short (e.g. logos with text "IBM")
    if len(alt_text.strip()) <= 2:
        return True

    # URLs or file paths
    if alt_lower.startswith(('http://', 'https://', '/', './', '../', 'www.')):
        return True

    return False


def get_alt_text_quality_message(alt_text: str) -> str:
    """Get a helpful message about why alt text is considered generic

    Args:
        alt_text: The generic alt text

    Returns:
        A descriptive message explaining the issue
    """
    alt_lower = alt_text.lower().strip()

    # Filename
    if any(ext in alt_lower for ext in ['.jpg', '.jpeg', '.png', '.gif', '.svg']):
        return f'Uses filename "{alt_text}" instead of description'

    # Generic word
    if alt_lower in ['image', 'photo', 'picture', 'graphic']:
        return f'Generic word "{alt_text}" doesn\'t describe what the image shows'

    # Generic + number
    if re.match(r'^(image|photo|picture|figure)\s*\d+$', alt_lower):
        return f'Generic label "{alt_text}" with no actual description'

    # Very short
    if len(alt_text.strip()) <= 2:
        return f'Too short to be descriptive: "{alt_text}"'

    # URL
    if alt_lower.startswith(('http://', 'https://')):
        return f'Uses URL "{alt_text[:50]}..." instead of description'

    # Default
    return f'Generic/non-descriptive: "{alt_text}"'


def get_better_alt_text_examples(alt_text: str, context: str = "image") -> str:
    """Provide examples of better alt text based on the generic text

    Args:
        alt_text: The generic alt text
        context: Context hint (e.g., "image", "chart", "logo")

    Returns:
        Examples of better alt text
    """
    alt_lower = alt_text.lower()

    if 'chart' in alt_lower or 'graph' in alt_lower:
        return """Good: "Bar chart comparing Q1-Q4 revenue, showing 23% growth"
Bad: "chart.png" or "graph1" """

    if 'logo' in alt_lower or context == "logo":
        return """Good: "Company Name Logo" or "Acme Corporation"
Bad: "logo.png" or "image1" """

    if 'screenshot' in alt_lower:
        return """Good: "Screenshot of settings panel showing dark mode toggle"
Bad: "screenshot.jpg" or "IMG_1234" """

    if 'photo' in alt_lower or 'picture' in alt_lower:
        return """Good: "Team photo from 2024 holiday party in the main office"
Bad: "photo1.jpg" or "DSC_5678" """

    # Default examples
    return """Good: Describe what the image shows and its purpose
Bad: Filenames, generic words, or placeholder text"""


# Link Text Quality Checking
# ===========================

def is_generic_link_text(link_text: str) -> bool:
    """Check if link text appears to be generic/non-descriptive

    Args:
        link_text: The link text to check

    Returns:
        True if the link text appears generic, False if it seems descriptive
    """
    if not link_text:
        return False

    text_lower = link_text.lower().strip()

    # Common generic link phrases
    generic_phrases = [
        # Click/action words alone
        "click here", "click this", "click", "tap here", "tap this",
        # Generic directions
        "here", "there", "this", "that",
        # Vague calls to action
        "read more", "learn more", "more", "more info", "more information",
        "see more", "view more", "find out more",
        # Generic download/document links
        "download", "download here", "download now", "get it here",
        "pdf", "document", "file",
        # Just "link"
        "link", "hyperlink", "url",
        # Generic navigation
        "continue", "next", "previous", "back", "go",
        # Single letters/numbers
        "a", "b", "c", "1", "2", "3",
    ]

    if text_lower in generic_phrases:
        return True

    # URLs as link text (the whole link is a URL)
    if text_lower.startswith(('http://', 'https://', 'www.', 'ftp://')):
        return True

    # Email addresses as link text
    if '@' in text_lower and '.' in text_lower and len(text_lower.split()) == 1:
        return True

    # Very short non-descriptive text (1-2 characters)
    if len(link_text.strip()) <= 2:
        return True

    # Page numbers only
    if re.match(r'^page\s*\d+$', text_lower):
        return True

    # Just punctuation or numbers
    if re.match(r'^[\d\s\-_.,:;!?]+$', link_text):
        return True

    return False


def get_link_text_quality_message(link_text: str) -> str:
    """Get a helpful message about why link text is considered generic

    Args:
        link_text: The generic link text

    Returns:
        A descriptive message explaining the issue
    """
    text_lower = link_text.lower().strip()

    # Click here variants
    if 'click' in text_lower or text_lower in ['here', 'there']:
        return f'Generic phrase "{link_text}" doesn\'t describe destination'

    # Read/learn more
    if 'more' in text_lower or text_lower in ['read', 'learn', 'see']:
        return f'Vague "{link_text}" doesn\'t indicate what user will find'

    # URL
    if text_lower.startswith(('http://', 'https://', 'www.')):
        return f'Raw URL "{link_text[:40]}..." is not descriptive for screen readers'

    # Email
    if '@' in text_lower:
        return f'Email address "{link_text}" - should use contact name instead'

    # Very short
    if len(link_text.strip()) <= 2:
        return f'Too short to be meaningful: "{link_text}"'

    # Download
    if text_lower in ['download', 'pdf', 'document']:
        return f'Generic "{link_text}" doesn\'t describe what document'

    # Default
    return f'Non-descriptive link text: "{link_text}"'


def get_better_link_text_examples(link_text: str, context: str = "") -> str:
    """Provide examples of better link text based on the generic text

    Args:
        link_text: The generic link text
        context: Context hint if available

    Returns:
        Examples of better link text
    """
    text_lower = link_text.lower()

    if 'click here' in text_lower or text_lower in ['here', 'there', 'this']:
        return """Good: "Download the 2024 Annual Report (PDF, 2.3 MB)"
Bad: "Click here to download" or "Here" """

    if 'more' in text_lower:
        return """Good: "Read our accessibility policy" or "Learn about WCAG 2.2 requirements"
Bad: "Read more" or "Learn more" """

    if text_lower.startswith(('http://', 'https://')):
        return """Good: "W3C Web Accessibility Initiative" or "Contact support team"
Bad: "https://www.w3.org/WAI/" or the full URL """

    if 'download' in text_lower or 'pdf' in text_lower:
        return """Good: "Product specification sheet (PDF)" or "Installation guide (3 pages)"
Bad: "Download" or "PDF" """

    # Default
    return """Good: Describe the destination or action clearly
Bad: Generic phrases, URLs, or vague calls to action"""
