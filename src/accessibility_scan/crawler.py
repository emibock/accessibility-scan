"""Page discovery via crawling"""

import asyncio
from typing import Dict, List, Set
from urllib.parse import urljoin, urlparse
from playwright.async_api import async_playwright, Page


class Crawler:
    """Discover pages by following links"""

    def __init__(self, config: Dict):
        self.config = config
        self.max_pages = config.get("max_pages", 50)
        self.start_url = config["start_url"]
        self.base_domain = urlparse(self.start_url).netloc
        self.visited: Set[str] = set()
        self.discovered: Set[str] = set()

    async def crawl(self) -> List[str]:
        """Crawl and discover pages"""
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

            # Start crawling
            await self._crawl_page(page, self.start_url)

            await browser.close()
            return list(self.discovered)[:self.max_pages]

    async def _crawl_page(self, page: Page, url: str):
        """Recursively crawl from URL"""
        if url in self.visited or len(self.visited) >= self.max_pages:
            return

        self.visited.add(url)
        self.discovered.add(url)

        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
        except Exception:
            return

        # Extract links
        links = await page.evaluate("""() => {
            return Array.from(document.querySelectorAll('a[href]'))
                .map(a => a.href)
                .filter(href => href.startsWith('http'));
        }""")

        # Filter links to same domain
        for link in links:
            if len(self.visited) >= self.max_pages:
                break

            if urlparse(link).netloc == self.base_domain:
                normalized = link.split('#')[0].split('?')[0]
                if normalized not in self.visited:
                    await self._crawl_page(page, normalized)

    async def _authenticate(self, page: Page, auth: Dict):
        """Handle authentication"""
        login_url = auth.get("login_url")
        if not login_url:
            return

        await page.goto(login_url)

        username_sel = auth.get("username_selector", "input[name='username']")
        password_sel = auth.get("password_selector", "input[name='password']")
        submit_sel = auth.get("submit_selector", "button[type='submit']")

        await page.fill(username_sel, auth["username"])
        await page.fill(password_sel, auth["password"])
        await page.click(submit_sel)

        success = auth.get("success_indicator")
        if success:
            await page.wait_for_selector(success, timeout=10000)
