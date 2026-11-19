"""WCAG 2.1 scanning using axe-playwright"""

import asyncio
from pathlib import Path
from typing import Callable, Dict, List, Optional
from playwright.async_api import async_playwright, Page
from axe_playwright_python.async_playwright import Axe


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

        return {
            "url": url,
            "violations": response.get("violations", []),
            "passes": len(response.get("passes", [])),
            "inapplicable": len(response.get("inapplicable", [])),
            "incomplete": len(response.get("incomplete", [])),
            "wcag_level": self.wcag_level
        }

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
        """Handle authentication"""
        login_url = auth.get("login_url")
        username = auth.get("username")
        password = auth.get("password")
        submit_sel = auth.get("submit_selector")

        has_credentials = bool(username and password)

        # Skip auth if no login URL, or no credentials and no explicit submit
        # selector to click (click-only auth must not fall back to a default
        # selector - the button has to be named explicitly)
        if not login_url or not (has_credentials or submit_sel):
            return

        await page.goto(login_url)

        if has_credentials:
            # Fill credentials - use defaults if selectors empty
            username_sel = auth.get("username_selector") or "input[name='username']"
            password_sel = auth.get("password_selector") or "input[name='password']"
            submit_sel = submit_sel or "button[type='submit']"

            await page.fill(username_sel, auth["username"])
            await page.fill(password_sel, auth["password"])

        # Click-only auth (guest/SSO): just click the sign-in button,
        # no credential fields to fill
        await page.click(submit_sel)

        # Wait for success indicator
        success = auth.get("success_indicator")
        if success:
            await page.wait_for_selector(success, timeout=10000)
