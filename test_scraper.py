#!/usr/bin/env python3
"""Unit tests for google-search-scraper."""

import json
import os
import tempfile
import unittest
from scraper import GoogleSearchScraper, ScrapedItem, generate_uule, clean_url, extract_domain


class TestGoogleSearchScraper(unittest.TestCase):

    def test_clean_url(self):
        raw1 = "/url?q=https://example.com/page&sa=U&ved=123"
        self.assertEqual(clean_url(raw1), "https://example.com/page")

        raw2 = "https://www.google.com/url?url=https://target.com/test"
        self.assertEqual(clean_url(raw2), "https://target.com/test")

        raw3 = "https://direct.com/article"
        self.assertEqual(clean_url(raw3), "https://direct.com/article")

    def test_extract_domain(self):
        self.assertEqual(extract_domain("https://www.salesforce.com/crm/"), "salesforce.com")
        self.assertEqual(extract_domain("http://subdomain.example.co.uk/test"), "subdomain.example.co.uk")

    def test_generate_uule(self):
        uule = generate_uule("New York,United States")
        self.assertTrue(uule.startswith("w+CAIQICI"))
        uule_uk = generate_uule("London,United Kingdom")
        self.assertTrue(uule_uk.startswith("w+CAIQICI"))

    def test_build_search_url(self):
        scraper = GoogleSearchScraper(
            country="uk",
            language="en",
            location="London,United Kingdom",
            domain="google.co.uk",
            num_per_page=10
        )
        url = scraper.build_search_url("best CRM software", start=10)
        self.assertIn("google.co.uk/search?", url)
        self.assertIn("q=best+CRM+software", url)
        self.assertIn("hl=en", url)
        self.assertIn("gl=uk", url)
        self.assertIn("start=10", url)
        self.assertIn("cr=countryUK", url)
        self.assertIn("uule=", url)

    def test_parse_results_with_mock_html(self):
        mock_html = """
        <html>
        <body>
            <div class="g">
                <h3><a href="https://www.hubspot.com/products/crm">HubSpot CRM System</a></h3>
                <div class="VwiC3b">HubSpot offer flexible CRM software for growing teams.</div>
            </div>
            <div class="MjjYud">
                <div class="tF2Cxc">
                    <h3><a href="/url?q=https://www.salesforce.com/crm/&sa=U">Salesforce CRM Solutions</a></h3>
                    <div class="IsZvec">Salesforce is the world's #1 customer relationship management platform.</div>
                </div>
            </div>
            <div class="g">
                <h3><a href="https://www.zoho.com/crm/">Zoho CRM Software</a></h3>
                <div class="description">Supercharge your sales team with Zoho CRM.</div>
            </div>
        </body>
        </html>
        """
        scraper = GoogleSearchScraper(country="us", language="en")
        items = scraper.parse_results(mock_html, current_count=0)

        self.assertEqual(len(items), 3)

        self.assertEqual(items[0].position, 1)
        self.assertEqual(items[0].title, "HubSpot CRM System")
        self.assertEqual(items[0].url, "https://www.hubspot.com/products/crm")
        self.assertEqual(items[0].domain, "hubspot.com")
        self.assertEqual(items[0].description, "HubSpot offer flexible CRM software for growing teams.")

        self.assertEqual(items[1].position, 2)
        self.assertEqual(items[1].title, "Salesforce CRM Solutions")
        self.assertEqual(items[1].url, "https://www.salesforce.com/crm/")
        self.assertEqual(items[1].domain, "salesforce.com")

        self.assertEqual(items[2].position, 3)
        self.assertEqual(items[2].title, "Zoho CRM Software")
        self.assertEqual(items[2].url, "https://www.zoho.com/crm/")

    def test_export_json_and_csv(self):
        scraper = GoogleSearchScraper()
        item = ScrapedItem(
            id="123",
            position=1,
            title="Test Title",
            description="Test Desc",
            url="https://test.com",
            domain="test.com",
            metadata={"country": "us", "language": "en"}
        )
        scraper.results = [item]

        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = os.path.join(tmpdir, "out.json")
            csv_path = os.path.join(tmpdir, "out.csv")

            scraper.export(json_path, fmt="json")
            self.assertTrue(os.path.exists(json_path))
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.assertEqual(len(data), 1)
                self.assertEqual(data[0]["title"], "Test Title")

            scraper.export(csv_path, fmt="csv")
            self.assertTrue(os.path.exists(csv_path))
            with open(csv_path, "r", encoding="utf-8") as f:
                content = f.read()
                self.assertIn("Test Title", content)
                self.assertIn("meta_country", content)


if __name__ == "__main__":
    unittest.main()
