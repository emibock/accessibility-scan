"""WCAG 2.1 scanning using axe-playwright"""

import asyncio
from pathlib import Path
from typing import Callable, Dict, List, Optional
from playwright.async_api import async_playwright, Page
from axe_playwright_python.async_playwright import Axe

from .alt_text_checker import (
    is_generic_alt_text,
    get_alt_text_quality_message,
    get_better_alt_text_examples,
)


class AccessibilityScanner:
    """Scanner for WCAG violations"""

    def __init__(self, config: Dict):
        self.config = config
        self.results = []
        self.wcag_level = config.get("wcag_level", "2.2")

    def _get_wcag_tags(self) -> List[str]:
        """Get axe-core tags for the specified WCAG level"""
        # Map WCAG levels to axe-core tags
        # Each level includes A and AA conformance levels (AAA is rarely required)
        tag_map = {
            "2.0": ["wcag2a", "wcag2aa"],
            "2.1": ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"],
            "2.2": ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22a", "wcag22aa"],
        }
        return tag_map.get(self.wcag_level, tag_map["2.2"])

    async def scan_page(self, page: Page, url: str) -> Dict:
        """Scan single page for violations"""
        # Use "load" instead of "networkidle" - many sites never reach networkidle
        # due to ads, analytics, etc. "load" waits for DOMContentLoaded + all resources
        await page.goto(url, wait_until="load", timeout=30000)

        # Optional settle delay for SPAs (React, Vue, Angular, Backstage, etc.)
        # Some client-rendered apps haven't painted content immediately after "load"
        settle_ms = self.config.get("settle_ms", 0)
        if settle_ms > 0:
            await asyncio.sleep(settle_ms / 1000.0)

        axe = Axe()

        # Configure axe to run only rules for the specified WCAG level
        tags = self._get_wcag_tags()
        axe_options = {
            "runOnly": {
                "type": "tag",
                "values": tags
            }
        }

        results = await axe.run(page, options=axe_options)

        # axe-playwright-python returns AxeResults object with .response dict
        response = results.response

        # Get violations from axe
        violations = response.get("violations", [])

        # Additional check: Detect generic alt text (axe catches missing alt, we catch bad alt)
        generic_alt_violation = await self._check_generic_alt_text(page, url)
        if generic_alt_violation:
            violations.append(generic_alt_violation)

        return {
            "url": url,
            "violations": violations,
            "passes": len(response.get("passes", [])),
            "inapplicable": len(response.get("inapplicable", [])),
            "incomplete": len(response.get("incomplete", [])),
            "wcag_level": self.wcag_level
        }

    async def _check_generic_alt_text(self, page: Page, url: str) -> Optional[Dict]:
        """Check for images with generic/non-descriptive alt text

        SEVERITY: MODERATE - Images have alt text, but it's not descriptive
        """
        try:
            # Extract all images with alt attributes
            images_with_alt = await page.evaluate('''
                () => {
                    const images = Array.from(document.querySelectorAll('img[alt]'));
                    return images.map((img, index) => ({
                        alt: img.alt,
                        src: img.src,
                        selector: `img:nth-of-type(${index + 1})`,
                        hasAlt: Boolean(img.alt && img.alt.trim())
                    })).filter(img => img.hasAlt); // Only images WITH alt text
                }
            ''')

            if not images_with_alt:
                return None

            # Check which ones have generic alt text
            generic_images = []
            for img in images_with_alt:
                alt_text = img['alt'].strip()
                if is_generic_alt_text(alt_text):
                    generic_images.append({
                        'alt': alt_text,
                        'src': img['src'],
                        'selector': img['selector'],
                        'reason': get_alt_text_quality_message(alt_text)
                    })

            if not generic_images:
                return None

            # Build helpful examples list
            examples = []
            for img in generic_images[:10]:  # Limit to first 10
                src_display = img['src'][:60] + '...' if len(img['src']) > 60 else img['src']
                examples.append(f'  - "{img["alt"]}" on {src_display}')
                examples.append(f'    Issue: {img["reason"]}')

            examples_text = '\n'.join(examples)
            if len(generic_images) > 10:
                examples_text += f'\n  ... and {len(generic_images) - 10} more'

            # Create violation in axe-core format
            return {
                "id": "web-images-generic-alt",
                "impact": "moderate",
                "description": f"{len(generic_images)} images have generic or non-descriptive alt text",
                "help": f"""Found {len(generic_images)} of {len(images_with_alt)} images with generic alt text that doesn't meaningfully describe the image.

**GENERIC ALT TEXT FOUND:**
{examples_text}

**WHY THIS IS A PROBLEM:**
Alt text like "image", "photo", or filenames tells screen reader users nothing useful. While technically the images have alt attributes (passing axe-core checks), the actual text is non-descriptive - nearly as bad as missing alt text.

**GENERIC PATTERNS TO AVOID:**
- Filenames: "image.jpg", "IMG_1234.png", "photo.gif"
- Generic words: "image", "photo", "picture", "graphic"
- Just numbers: "1", "2", "figure1"
- Placeholder text: "image description", "alt text"
- URLs or file paths

**HOW TO FIX:**
Replace generic alt text with actual descriptions:

Bad: `<img src="chart.png" alt="chart.png">`
Good: `<img src="chart.png" alt="Bar chart showing website traffic growth from 2020-2024, increasing from 100K to 500K monthly visitors">`

Bad: `<img src="team.jpg" alt="photo">`
Good: `<img src="team.jpg" alt="Engineering team photo from 2024 company retreat">`

Bad: `<img src="logo.svg" alt="image1">`
Good: `<img src="logo.svg" alt="Acme Corporation logo">`

**WHAT MAKES GOOD ALT TEXT:**
✓ Describes what the image shows, not that it IS an image
✓ Conveys the same information a sighted user would get
✓ Concise but complete (aim for 1-2 sentences)
✓ Provides context relevant to the page content

**FOR DECORATIVE IMAGES:**
If the image is purely decorative (adds no information):
- Use empty alt: `<img src="decoration.png" alt="">`
- Or use CSS background images instead
- Do NOT use generic text like "decorative image"

**MODERATE SEVERITY:**
This is a usability issue, not a critical barrier. Screen readers will announce the generic text, but users won't understand what the image shows. It makes navigation slower and less efficient.

**WHAT THIS FIXES:**
Ensures screen reader users get meaningful image descriptions, not useless generic text or filenames.""",
                "helpUrl": "https://www.w3.org/WAI/WCAG21/Techniques/html/H37",
                "tags": ["wcag2a", "wcag111", "quality", "cat.text-alternatives"],
                "nodes": [{
                    "html": f"{len(generic_images)} images with generic alt text",
                    "target": [generic_images[0]['selector']] if generic_images else [],
                    "failureSummary": f"Found {len(generic_images)} images with non-descriptive alt text. Examples: {', '.join([f'"{img["alt"]}"' for img in generic_images[:3]])}. Alt text should describe the image content, not be a filename or generic word."
                }]
            }

        except Exception as e:
            # Generic alt check failed, skip
            return None

    async def scan(self, urls: List[str], progress_callback: Optional[Callable[[int, int], None]] = None) -> List[Dict]:
        """Scan multiple URLs with optional progress callback"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=self.config.get("headless", True)
            )

            context = await browser.new_context()
            page = await context.new_page()

            # Auth if needed
            auth = self.config.get("authentication")
            if auth:
                await self._authenticate(page, auth)

            results = []
            total = len(urls)
            for idx, url in enumerate(urls):
                try:
                    result = await self.scan_page(page, url)
                    results.append(result)
                except Exception as e:
                    results.append({
                        "url": url,
                        "error": str(e),
                        "violations": []
                    })

                # Report progress after each page
                if progress_callback:
                    progress_callback(idx + 1, total)

            await browser.close()
            return results

    async def _authenticate(self, page: Page, auth: Dict):
        """Handle authentication

        Supports both credential-based and click-only authentication:
        - Traditional: username + password + submit button
        - SSO/Guest: just click a button (no credentials)
        """
        login_url = auth.get("login_url")
        username = auth.get("username")
        password = auth.get("password")
        submit_sel = auth.get("submit_selector")

        # Skip auth if no login URL
        if not login_url:
            return

        # Must have either credentials OR a submit selector to click
        has_credentials = username and password
        has_submit = submit_sel is not None

        if not has_credentials and not has_submit:
            return

        await page.goto(login_url)

        # Fill credentials only if provided (supports click-only auth)
        if has_credentials:
            username_sel = auth.get("username_selector") or "input[name='username']"
            password_sel = auth.get("password_selector") or "input[name='password']"

            await page.fill(username_sel, username)
            await page.fill(password_sel, password)

        # Click submit if selector provided (required for both credential and click-only)
        if has_submit:
            # Use provided submit selector or default
            submit_selector = submit_sel or "button[type='submit']"
            await page.click(submit_selector)

        # Wait for success indicator
        success = auth.get("success_indicator")
        if success:
            await page.wait_for_selector(success, timeout=10000)
