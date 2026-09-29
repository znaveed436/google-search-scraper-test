#!/usr/bin/env python3
"""
google-search-scraper - Google Search Web Scraper
Google Search Scraper - Collect public SERP results, snippets, and ranking signals for SEO research

Sponsored by CoreClaw - https://www.coreclaw.com
"""

import argparse
import base64
import csv
import json
import random
import sys
import time
from dataclasses import dataclass, asdict, field
from typing import List, Optional, Dict, Any
from urllib.parse import quote_plus, urlparse, parse_qs, unquote

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Installing dependencies...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "beautifulsoup4", "lxml"])
    import requests
    from bs4 import BeautifulSoup


DEFAULT_USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3.1 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0',
]


def generate_uule(location: str) -> str:
    """
    Generate Google's Canonical Location UULE parameter.

    UULE format: w+CAIQICI + <LengthKey> + Base64(Location)
    where LengthKey is secret_keys[len(location) % len(secret_keys)].
    """
    if not location:
        return ""
    secret_keys = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_'
    length = len(location)
    key = secret_keys[length % len(secret_keys)]
    encoded = base64.b64encode(location.encode('utf-8')).decode('utf-8')
    return f"w+CAIQICI{key}{encoded}"


def clean_url(raw_url: str) -> str:
    """Clean Google redirect links (/url?q=...) to direct destination URLs."""
    if not raw_url:
        return ""
    if raw_url.startswith('/url?') or raw_url.startswith('https://www.google.com/url?') or raw_url.startswith('http://www.google.com/url?'):
        parsed = urlparse(raw_url)
        qs = parse_qs(parsed.query)
        if 'q' in qs and qs['q']:
            return qs['q'][0]
        if 'url' in qs and qs['url']:
            return qs['url'][0]
    return raw_url


def extract_domain(url: str) -> str:
    """Extract domain name from a URL."""
    try:
        netloc = urlparse(url).netloc
        if netloc.startswith('www.'):
            netloc = netloc[4:]
        return netloc
    except Exception:
        return ""


@dataclass
class ScrapedItem:
    """Data model for scraped Google Search items."""
    id: str = ""
    position: int = 0
    title: str = ""
    description: str = ""
    url: str = ""
    domain: str = ""
    date: str = ""
    author: str = ""
    rating: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    scraped_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class GoogleSearchScraper:
    """Main scraper class for Google Search data extraction."""

    def __init__(
        self,
        proxy: Optional[str] = None,
        timeout: int = 30,
        delay: float = 1.0,
        user_agent: Optional[str] = None,
        country: str = 'us',
        language: str = 'en',
        location: Optional[str] = None,
        domain: str = 'google.com',
        num_per_page: int = 10,
        max_retries: int = 3
    ):
        self.session = requests.Session()
        self.user_agent = user_agent or random.choice(DEFAULT_USER_AGENTS)
        self.session.headers.update({
            'User-Agent': self.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': f'{language}-{country.upper()},{language};q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
        })
        self.proxy = proxy
        self.timeout = timeout
        self.delay = delay
        self.country = country.lower()
        self.language = language.lower()
        self.location = location
        self.domain = domain.replace('https://', '').replace('http://', '').strip('/')
        self.num_per_page = num_per_page
        self.max_retries = max_retries
        self.results: List[ScrapedItem] = []

    def _get_proxies(self) -> Optional[dict]:
        if self.proxy:
            return {"http": self.proxy, "https": self.proxy}
        return None

    def build_search_url(self, query: str, start: int = 0) -> str:
        """Construct the Google search URL with proper country, language, and location parameters."""
        base_domain = self.domain if self.domain else 'google.com'
        encoded_query = quote_plus(query)
        url = (
            f"https://www.{base_domain}/search?"
            f"q={encoded_query}"
            f"&hl={self.language}"
            f"&gl={self.country}"
            f"&start={start}"
            f"&num={self.num_per_page}"
        )
        if self.country and self.country != 'us':
            url += f"&cr=country{self.country.upper()}"

        if self.location:
            uule = generate_uule(self.location)
            if uule:
                url += f"&uule={quote_plus(uule)}"

        return url

    def fetch_page(self, url: str) -> Optional[str]:
        """Fetch HTML content from a URL with retries."""
        for attempt in range(1, self.max_retries + 1):
            try:
                if self.delay > 0:
                    time.sleep(self.delay)
                resp = self.session.get(url, proxies=self._get_proxies(), timeout=self.timeout)
                resp.raise_for_status()
                return resp.text
            except requests.RequestException as e:
                print(f"Error fetching {url} (attempt {attempt}/{self.max_retries}): {e}")
                if attempt < self.max_retries:
                    time.sleep(self.delay * attempt)
        return None

    def parse_results(self, html: str, current_count: int = 0) -> List[ScrapedItem]:
        """Parse HTML content and extract data items."""
        soup = BeautifulSoup(html, 'lxml' if 'lxml' in sys.modules else 'html.parser')
        items = []
        timestamp = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())

        # Selectors matching Google Search result blocks across various SERP layouts
        containers = soup.select('div.g, div.MjjYud, div.tF2Cxc, div.Vkp21b, [data-testid="result"]')

        # If standard containers are not matched, look for any container with an h3 and a link
        if not containers:
            candidate_h3s = soup.find_all('h3')
            seen_parents = set()
            for h3 in candidate_h3s:
                parent = h3.find_parent('div')
                if parent and id(parent) not in seen_parents:
                    seen_parents.add(id(parent))
                    containers.append(parent)

        position = current_count + 1
        seen_urls = set(item.url for item in self.results)

        for elem in containers:
            title_elem = elem.select_one('h3, [role="heading"], .title, [data-testid="title"]')
            link_elem = elem.select_one('a[href]')

            if not title_elem or not link_elem:
                continue

            raw_url = link_elem.get('href', '')
            final_url = clean_url(raw_url)

            # Skip internal Google links, empty URLs, or duplicates
            if not final_url or not final_url.startswith('http') or 'google.com/search' in final_url:
                continue

            if final_url in seen_urls:
                continue

            title = title_elem.get_text(strip=True)
            if not title:
                continue

            # Extract snippet / description
            desc_elem = elem.select_one('.VwiC3b, .s, .IsZvec, .yD340b, .MUxG3d, .description, .summary, p')
            description = desc_elem.get_text(strip=True) if desc_elem else ""

            domain_name = extract_domain(final_url)
            item_id = str(hash(f"{final_url}:{title}"))[:12].replace('-', 'x')

            item = ScrapedItem(
                id=item_id,
                position=position,
                title=title,
                description=description,
                url=final_url,
                domain=domain_name,
                metadata={
                    "country": self.country,
                    "language": self.language,
                    "location": self.location or ""
                },
                scraped_at=timestamp
            )
            items.append(item)
            seen_urls.add(final_url)
            position += 1

        return items

    def scrape(self, query: str, max_results: int = 100) -> List[ScrapedItem]:
        """Scrape Google Search data for a given query."""
        self.results = []
        page = 0

        while len(self.results) < max_results:
            start = page * self.num_per_page
            url = self.build_search_url(query, start=start)
            print(f"Scraping page {page + 1}... ({len(self.results)}/{max_results})")

            html = self.fetch_page(url)
            if not html:
                break

            items = self.parse_results(html, current_count=len(self.results))
            if not items:
                print("No more results found.")
                break

            self.results.extend(items)
            page += 1

            # Avoid infinite loop if no new items are being added
            if len(items) == 0:
                break

        self.results = self.results[:max_results]
        return self.results

    def export(self, filepath: str, fmt: str = 'json') -> None:
        """Export results to JSON or CSV."""
        data = [item.to_dict() for item in self.results]
        if fmt == 'csv':
            if not data:
                print("No data to export.")
                return

            # Flatten metadata field for CSV
            csv_data = []
            for row in data:
                flat_row = row.copy()
                meta = flat_row.pop('metadata', {})
                if isinstance(meta, dict):
                    for k, v in meta.items():
                        flat_row[f"meta_{k}"] = v
                csv_data.append(flat_row)

            keys = csv_data[0].keys()
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=keys)
                writer.writeheader()
                writer.writerows(csv_data)
        else:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Exported {len(data)} records to {filepath}")


def main():
    parser = argparse.ArgumentParser(description='google-search-scraper - Google Search Web Scraper')
    parser.add_argument('--query', '-q', required=True, help='Search query or URL')
    parser.add_argument('--output', '-o', default='output.json', help='Output file path')
    parser.add_argument('--format', '-f', choices=['json', 'csv'], default='json', help='Output format')
    parser.add_argument('--max-results', '-m', type=int, default=100, help='Max results')
    parser.add_argument('--delay', '-d', type=float, default=1.0, help='Delay between requests')
    parser.add_argument('--proxy', '-p', default=None, help='Proxy URL')
    parser.add_argument('--timeout', '-t', type=int, default=30, help='Request timeout')
    parser.add_argument('--user-agent', '-ua', default=None, help='Custom User-Agent header')
    parser.add_argument('--country', '-c', default='us', help='Country code (e.g. us, uk, ca, de, fr)')
    parser.add_argument('--language', '-l', default='en', help='Language code (e.g. en, es, fr, de)')
    parser.add_argument('--location', '-loc', default=None, help='Target location string (e.g. "New York,United States")')
    parser.add_argument('--domain', default='google.com', help='Google domain (e.g. google.com, google.co.uk)')
    parser.add_argument('--quiet', action='store_true', help='Suppress output')
    args = parser.parse_args()

    scraper = GoogleSearchScraper(
        proxy=args.proxy,
        timeout=args.timeout,
        delay=args.delay,
        user_agent=args.user_agent,
        country=args.country,
        language=args.language,
        location=args.location,
        domain=args.domain
    )
    scraper.scrape(args.query, args.max_results)
    scraper.export(args.output, args.format)

    if not args.quiet:
        print(f"Done! Scraped {len(scraper.results)} items from Google Search.")


if __name__ == '__main__':
    main()
