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

    async def scan_page(self, page: Page, url: str) -> Dict:
        """Scan single page for violations"""
        # Use "load" instead of "networkidle" - many sites never reach networkidle
        # due to ads, analytics, etc. "load" waits for DOMContentLoaded + all resources
        await page.goto(url, wait_until="load", timeout=30000)

        axe = Axe()
        results = await axe.run(page)

        # axe-playwright-python returns AxeResults object with .response dict
        response = results.response

        return {
            "url": url,
            "violations": response.get("violations", []),
            "passes": len(response.get("passes", [])),
            "inapplicable": len(response.get("inapplicable", [])),
            "incomplete": len(response.get("incomplete", []))
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

        # Skip auth if no login URL or no credentials
        if not login_url or not username or not password:
            return

        await page.goto(login_url)

        # Fill credentials - use defaults if selectors empty
        username_sel = auth.get("username_selector") or "input[name='username']"
        password_sel = auth.get("password_selector") or "input[name='password']"
        submit_sel = auth.get("submit_selector") or "button[type='submit']"

        await page.fill(username_sel, auth["username"])
        await page.fill(password_sel, auth["password"])
        await page.click(submit_sel)

        # Wait for success indicator
        success = auth.get("success_indicator")
        if success:
            await page.wait_for_selector(success, timeout=10000)
