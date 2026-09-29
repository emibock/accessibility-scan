"""WCAG 2.1 scanning using axe-playwright"""

import asyncio
from pathlib import Path
from typing import Dict, List
from playwright.async_api import async_playwright, Page
from axe_playwright_python.async_playwright import Axe


class AccessibilityScanner:
    """Scanner for WCAG violations"""

    def __init__(self, config: Dict):
        self.config = config
        self.results = []

    async def scan_page(self, page: Page, url: str) -> Dict:
        """Scan single page for violations"""
        await page.goto(url, wait_until="networkidle", timeout=30000)

        axe = Axe()
        results = await axe.run(page)

        return {
            "url": url,
            "violations": results.violations,
            "passes": len(results.passes),
            "inapplicable": len(results.inapplicable),
            "incomplete": len(results.incomplete)
        }

    async def scan(self, urls: List[str]) -> List[Dict]:
        """Scan multiple URLs"""
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
            for url in urls:
                try:
                    result = await self.scan_page(page, url)
                    results.append(result)
                except Exception as e:
                    results.append({
                        "url": url,
                        "error": str(e),
                        "violations": []
                    })

            await browser.close()
            return results

    async def _authenticate(self, page: Page, auth: Dict):
        """Handle authentication"""
        login_url = auth.get("login_url")
        if not login_url:
            return

        await page.goto(login_url)

        # Fill credentials
        username_sel = auth.get("username_selector", "input[name='username']")
        password_sel = auth.get("password_selector", "input[name='password']")
        submit_sel = auth.get("submit_selector", "button[type='submit']")

        await page.fill(username_sel, auth["username"])
        await page.fill(password_sel, auth["password"])
        await page.click(submit_sel)

        # Wait for success indicator
        success = auth.get("success_indicator")
        if success:
            await page.wait_for_selector(success, timeout=10000)
