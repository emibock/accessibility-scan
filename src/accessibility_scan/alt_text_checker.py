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
