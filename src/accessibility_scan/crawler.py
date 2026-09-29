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
        self.to_visit: List[str] = []
        self.verbose = config.get("verbose", False)

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

            # Queue-based crawling (not recursive)
            self.to_visit = [self.start_url]

            while self.to_visit and len(self.visited) < self.max_pages:
                url = self.to_visit.pop(0)

                if url in self.visited:
                    continue

                if self.verbose:
                    print(f"Crawling: {url}")

                await self._crawl_page(page, url)

            await browser.close()

            if self.verbose:
                print(f"\nCrawl complete: {len(self.discovered)} pages discovered")

            return list(self.discovered)[:self.max_pages]

    async def _crawl_page(self, page: Page, url: str):
        """Crawl single page and extract links"""
        if url in self.visited:
            return

        self.visited.add(url)
        self.discovered.add(url)

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(1000)  # Let page settle
        except Exception as e:
            if self.verbose:
                print(f"  Error loading {url}: {e}")
            return

        # Extract links
        try:
            links = await page.evaluate("""() => {
                return Array.from(document.querySelectorAll('a[href]'))
                    .map(a => a.href)
                    .filter(href => href && href.startsWith('http'));
            }""")

            if self.verbose:
                print(f"  Found {len(links)} links")

        except Exception as e:
            if self.verbose:
                print(f"  Error extracting links: {e}")
            return

        # Add same-domain links to queue
        new_links = 0
        for link in links:
            if len(self.visited) + len(self.to_visit) >= self.max_pages:
                break

            parsed = urlparse(link)
            if parsed.netloc == self.base_domain:
                # Normalize: remove fragments and query params
                normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                normalized = normalized.rstrip('/')

                if normalized and normalized not in self.visited and normalized not in self.to_visit:
                    self.to_visit.append(normalized)
                    new_links += 1

        if self.verbose and new_links > 0:
            print(f"  Added {new_links} new links to queue")

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
