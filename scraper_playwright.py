#!/usr/bin/env python3
"""
google-search-scraper - Playwright-based Google Search SERP Scraper
Collect public SERP results using headless browser automation (Playwright).

This version uses a headless browser to mimic real user behavior, avoiding Google's bot detection.
Install: pip install playwright && playwright install
"""

import argparse
import csv
import json
import random
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("Installing playwright...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "playwright"])
    subprocess.check_call([sys.executable, "-m", "playwright", "install"])
    from playwright.sync_api import sync_playwright


GOOGLE_COUNTRY_DOMAINS = {
    "us": "google.com",
    "uk": "google.co.uk",
    "gb": "google.co.uk",
    "ca": "google.ca",
    "au": "google.com.au",
    "de": "google.de",
    "fr": "google.fr",
    "in": "google.co.in",
    "br": "google.com.br",
    "mx": "google.com.mx",
    "es": "google.es",
    "it": "google.it",
    "jp": "google.co.jp",
    "kr": "google.co.kr",
    "nl": "google.nl",
    "se": "google.se",
    "no": "google.no",
    "dk": "google.dk",
    "ie": "google.ie",
    "nz": "google.co.nz",
    "sg": "google.com.sg",
    "ae": "google.ae",
}

GOOGLE_COUNTRY_CODES = {
    "us": "US",
    "uk": "GB",
    "gb": "GB",
    "ca": "CA",
    "au": "AU",
    "de": "DE",
    "fr": "FR",
    "in": "IN",
    "br": "BR",
    "mx": "MX",
    "es": "ES",
    "it": "IT",
    "jp": "JP",
    "kr": "KR",
    "nl": "NL",
    "se": "SE",
    "no": "NO",
    "dk": "DK",
    "ie": "IE",
    "nz": "NZ",
    "sg": "SG",
    "ae": "AE",
}

DEFAULT_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
]


def get_google_domain(country: str) -> str:
    """Get the correct Google domain for a country."""
    country = country.lower()
    return GOOGLE_COUNTRY_DOMAINS.get(country, "google.com")


def extract_domain(url: str) -> str:
    """Extract domain from a URL."""
    try:
        from urllib.parse import urlparse
        netloc = urlparse(url).netloc
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return netloc
    except Exception:
        return ""


@dataclass
class ScrapedItem:
    id: str = ""
    position: int = 0
    title: str = ""
    description: str = ""
    url: str = ""
    domain: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    scraped_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class PlaywrightGoogleScraper:
    def __init__(
        self,
        timeout: int = 60000,
        delay: float = 1.0,
        user_agent: Optional[str] = None,
        country: str = "us",
        language: str = "en",
        headless: bool = True,
    ):
        self.timeout = timeout
        self.delay = delay
        self.user_agent = user_agent or random.choice(DEFAULT_USER_AGENTS)
        self.country = country.lower()
        self.language = language.lower()
        self.headless = headless
        self.google_domain = get_google_domain(country)
        self.results: List[ScrapedItem] = []

    def scrape(self, query: str, max_results: int = 10) -> List[ScrapedItem]:
        """Scrape Google SERP using Playwright headless browser."""
        self.results = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            page = browser.new_page()

            # Set realistic headers
            page.set_extra_http_headers({
                "Accept-Language": f"{self.language}-{GOOGLE_COUNTRY_CODES.get(self.country, 'US')},{self.language};q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Referer": "https://www.google.com/",
            })
            page.set_user_agent(self.user_agent)
            page.set_viewport_size({"width": 1920, "height": 1080})

            try:
                # Build search URL
                search_url = f"https://www.{self.google_domain}/search?q={query.replace(' ', '+')}&hl={self.language}&gl={self.country}"
                
                print(f"Navigating to: {search_url}")
                page.goto(search_url, wait_until="domcontentloaded", timeout=self.timeout)

                # Wait for results to appear
                try:
                    page.wait_for_selector("h3", timeout=10000)
                except Exception as e:
                    print(f"No results found or page structure changed: {e}")
                    browser.close()
                    return self.results

                # Simulate human-like scrolling
                page.evaluate("() => window.scrollBy(0, window.innerHeight)")
                time.sleep(random.uniform(1, 3))

                # Extract results
                self._extract_results(page, query)

                # Paginate through results if needed
                page_num = 1
                while len(self.results) < max_results and page_num < 5:
                    try:
                        next_btn = page.query_selector("a[aria-label='Next page']")
                        if not next_btn:
                            break
                        next_btn.click()
                        page.wait_for_selector("h3", timeout=self.timeout)
                        page.evaluate("() => window.scrollBy(0, window.innerHeight)")
                        time.sleep(random.uniform(self.delay, self.delay * 2))
                        self._extract_results(page, query)
                        page_num += 1
                    except Exception as e:
                        print(f"Error navigating to next page: {e}")
                        break

            finally:
                browser.close()

        self.results = self.results[:max_results]
        return self.results

    def _extract_results(self, page, query: str) -> None:
        """Extract individual results from the current page."""
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        # Try multiple selectors for robustness
        result_selectors = [
            "div.g",
            "div.tF2Cxc",
            "div.MjjYud",
            "div.Vkp21b",
        ]

        result_divs = []
        for selector in result_selectors:
            divs = page.query_selector_all(selector)
            if divs:
                result_divs = divs
                break

        print(f"Found {len(result_divs)} result containers")

        position = len(self.results) + 1
        seen_urls = set(item.url for item in self.results)

        for i, result_div in enumerate(result_divs):
            try:
                # Extract title
                title_elem = result_div.query_selector("h3")
                if not title_elem:
                    continue
                title = title_elem.inner_text()
                if not title:
                    continue

                # Extract URL from parent link
                link_elem = result_div.query_selector("a[href]")
                if not link_elem:
                    continue
                url = link_elem.get_attribute("href")
                if not url or url.startswith("/url?"):
                    continue
                if "google.com/search" in url or url in seen_urls:
                    continue

                # Extract snippet/description
                desc_elem = result_div.query_selector("div.VwiC3b, div.s, div.IsZvec, p")
                description = desc_elem.inner_text() if desc_elem else ""

                domain = extract_domain(url)
                item_id = str(abs(hash(f"{url}:{title}")))[:12]

                item = ScrapedItem(
                    id=item_id,
                    position=position,
                    title=title,
                    description=description,
                    url=url,
                    domain=domain,
                    metadata={
                        "country": self.country,
                        "language": self.language,
                        "google_domain": self.google_domain,
                    },
                    scraped_at=timestamp,
                )
                self.results.append(item)
                seen_urls.add(url)
                position += 1
                print(f"  [{position - 1}] {title[:60]}...")

            except Exception as e:
                print(f"Error parsing result {i}: {e}")
                continue

    def export(self, filepath: str, fmt: str = "json") -> None:
        """Export results as JSON or CSV."""
        data = [item.to_dict() for item in self.results]
        
        if fmt == "csv":
            if not data:
                print("No data to export.")
                return

            csv_rows = []
            for row in data:
                flat_row = row.copy()
                meta = flat_row.pop("metadata", {})
                if isinstance(meta, dict):
                    for key, value in meta.items():
                        flat_row[f"meta_{key}"] = value
                csv_rows.append(flat_row)

            fieldnames = list(csv_rows[0].keys())
            with open(filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(csv_rows)
        else:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"Exported {len(data)} records to {filepath}")


def main():
    parser = argparse.ArgumentParser(description="google-search-scraper - Playwright-based Google SERP Scraper")
    parser.add_argument("--query", "-q", required=True, help="Search query")
    parser.add_argument("--output", "-o", default="output.json", help="Output file path")
    parser.add_argument("--format", "-f", choices=["json", "csv"], default="json", help="Output format")
    parser.add_argument("--max-results", "-m", type=int, default=10, help="Maximum number of results")
    parser.add_argument("--delay", "-d", type=float, default=1.5, help="Delay between page actions in seconds")
    parser.add_argument("--timeout", "-t", type=int, default=60, help="Page load timeout in seconds")
    parser.add_argument("--user-agent", "-ua", default=None, help="Custom User-Agent header")
    parser.add_argument("--country", "-c", default="us", help="Country code (e.g. us, uk, ca, de, fr)")
    parser.add_argument("--language", "-l", default="en", help="Language code (e.g. en, es, fr, de)")
    parser.add_argument("--headless", action="store_true", default=True, help="Run in headless mode")
    parser.add_argument("--no-headless", dest="headless", action="store_false", help="Show browser window (debug mode)")
    args = parser.parse_args()

    scraper = PlaywrightGoogleScraper(
        timeout=args.timeout * 1000,
        delay=args.delay,
        user_agent=args.user_agent,
        country=args.country,
        language=args.language,
        headless=args.headless,
    )
    
    print(f"Scraping '{args.query}' from {get_google_domain(args.country)} ({args.country.upper()})...")
    scraper.scrape(args.query, args.max_results)
    scraper.export(args.output, args.format)
    print(f"Done! Scraped {len(scraper.results)} items from Google Search.")


if __name__ == "__main__":
    main()
