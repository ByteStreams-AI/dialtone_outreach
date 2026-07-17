"""Tests for the Houston Yelp adapter."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from scraper.houston import scrape_houston, _business_to_lead, YELP_API_URL


def _make_biz(**kwargs) -> dict:
    base = {
        "name": "TACOS EL GORDO",
        "url": "https://yelp.com/biz/tacos-el-gordo",
        "phone": "+17135550101",
        "display_phone": "(713) 555-0101",
        "categories": [
            {"alias": "mexican", "title": "Mexican"},
            {"alias": "restaurants", "title": "Restaurants"},
        ],
        "transactions": ["delivery", "pickup"],
        "location": {
            "address1": "1234 Westheimer Rd",
            "address2": "",
            "city": "Houston",
            "state": "TX",
            "zip_code": "77006",
        },
    }
    base.update(kwargs)
    return base


SAMPLE_BUSINESSES = [
    _make_biz(),
    _make_biz(
        name="SUNRISE FOOD TRUCK",
        categories=[{"alias": "foodtrucks", "title": "Food Trucks"}],
        transactions=[],
        display_phone="(713) 555-0202",
        location={
            "address1": "5678 Main St",
            "city": "Houston",
            "state": "TX",
            "zip_code": "77002",
        },
    ),
    _make_biz(name="TACOS EL GORDO"),  # duplicate — should be deduplicated
    _make_biz(name=""),  # blank name — should be skipped
]

MOCK_RESPONSE = {"businesses": SAMPLE_BUSINESSES, "total": 4}


class HoustonAdapterTests(unittest.TestCase):
    def _mock_httpx(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_RESPONSE
        mock_resp.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_resp
        return mock_client

    @patch("scraper.houston._get_api_key", return_value="test-key")
    @patch("scraper.houston.httpx.Client")
    def test_returns_leads(self, mock_client_cls, _mock_key):
        mock_client_cls.return_value = self._mock_httpx()
        leads = scrape_houston(limit=10)
        names = [l.name for l in leads]
        self.assertIn("TACOS EL GORDO", names)
        self.assertIn("SUNRISE FOOD TRUCK", names)

    @patch("scraper.houston._get_api_key", return_value="test-key")
    @patch("scraper.houston.httpx.Client")
    def test_deduplicates_by_name(self, mock_client_cls, _mock_key):
        mock_client_cls.return_value = self._mock_httpx()
        leads = scrape_houston(limit=10)
        names = [l.name for l in leads]
        self.assertEqual(names.count("TACOS EL GORDO"), 1)

    @patch("scraper.houston._get_api_key", return_value="test-key")
    @patch("scraper.houston.httpx.Client")
    def test_skips_blank_names(self, mock_client_cls, _mock_key):
        mock_client_cls.return_value = self._mock_httpx()
        leads = scrape_houston(limit=10)
        self.assertTrue(all(l.name for l in leads))

    @patch("scraper.houston._get_api_key", return_value="test-key")
    @patch("scraper.houston.httpx.Client")
    def test_populates_fields(self, mock_client_cls, _mock_key):
        mock_client_cls.return_value = self._mock_httpx()
        leads = scrape_houston(limit=10)
        lead = next(l for l in leads if l.name == "TACOS EL GORDO")
        self.assertEqual(lead.city, "Houston")
        self.assertEqual(lead.phone, "(713) 555-0101")
        self.assertIn("Westheimer", lead.address)
        self.assertTrue(lead.offers_delivery)
        self.assertTrue(lead.offers_pickup)

    @patch("scraper.houston._get_api_key", return_value="test-key")
    @patch("scraper.houston.httpx.Client")
    def test_empty_response(self, mock_client_cls, _mock_key):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"businesses": []}
        mock_resp.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_resp
        mock_client_cls.return_value = mock_client
        leads = scrape_houston(limit=10)
        self.assertEqual(leads, [])

    def test_missing_api_key_raises(self):
        with self.assertRaises(ValueError) as ctx:
            from scraper.houston import _get_api_key
            import os

            os.environ.pop("YELP_API_KEY", None)
            _get_api_key()
        self.assertIn("YELP_API_KEY", str(ctx.exception))

    @patch("scraper.houston._get_api_key", return_value="test-key")
    @patch("scraper.houston.httpx.Client")
    def test_passes_limit_and_offset(self, mock_client_cls, _mock_key):
        mock_client = self._mock_httpx()
        mock_client_cls.return_value = mock_client
        scrape_houston(limit=25, offset=50)
        call_kwargs = mock_client.get.call_args
        params = call_kwargs[1].get("params") or call_kwargs[0][1]
        self.assertEqual(params["limit"], 25)
        self.assertEqual(params["offset"], 50)


if __name__ == "__main__":
    unittest.main()
