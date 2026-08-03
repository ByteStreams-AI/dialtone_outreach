import csv
import tempfile
import unittest
from pathlib import Path

from scraper.export import write_csv, write_json
from scraper.models import LeadItem


class CallPrepFieldTests(unittest.TestCase):
    def test_model_accepts_call_prep_fields(self) -> None:
        lead = LeadItem(
            name="Test Truck",
            source="https://example.com/listings",
            url="https://example.com/trucks/test-truck",
            city="Austin",
            has_website=True,
            has_app=False,
            offers_pickup=True,
            offers_delivery=True,
            delivery_platforms="DoorDash, Uber Eats",
            marketplace_providers="DoorDash, Uber Eats",
            first_party_ordering="ChowNow",
        )

        self.assertTrue(lead.has_website)
        self.assertFalse(lead.has_app)
        self.assertTrue(lead.offers_pickup)
        self.assertTrue(lead.offers_delivery)
        self.assertEqual(lead.delivery_platforms, "DoorDash, Uber Eats")
        self.assertEqual(lead.marketplace_providers, "DoorDash, Uber Eats")
        self.assertEqual(lead.first_party_ordering, "ChowNow")

    def test_csv_export_includes_call_prep_columns(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "leads.csv"
            lead = LeadItem(
                name="Test Truck",
                source="https://example.com/listings",
                url="https://example.com/trucks/test-truck",
                city="Austin",
                has_website=True,
                has_app=False,
                offers_pickup=True,
                offers_delivery=True,
                delivery_platforms="DoorDash",
                marketplace_providers="DoorDash",
                first_party_ordering=None,
            )

            write_csv(str(path), [lead])

            with path.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))

            self.assertEqual(len(rows), 1)
            self.assertIn("has_website", rows[0])
            self.assertIn("has_app", rows[0])
            self.assertIn("offers_pickup", rows[0])
            self.assertIn("offers_delivery", rows[0])
            self.assertIn("delivery_platforms", rows[0])
            self.assertIn("marketplace_providers", rows[0])
            self.assertIn("first_party_ordering", rows[0])

    def test_json_export_preserves_call_prep_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "leads.json"
            lead = LeadItem(
                name="Test Truck",
                source="https://example.com/listings",
                url="https://example.com/trucks/test-truck",
                city="Austin",
                has_website=True,
                has_app=False,
                offers_pickup=True,
                offers_delivery=True,
                delivery_platforms="Uber Eats",
                marketplace_providers="Uber Eats",
                first_party_ordering="ChowNow",
            )

            write_json(str(path), [lead])

            payload = path.read_text(encoding="utf-8")
            self.assertIn('"has_website": true', payload)
            self.assertIn('"has_app": false', payload)
            self.assertIn('"offers_pickup": true', payload)
            self.assertIn('"offers_delivery": true', payload)
            self.assertIn('"delivery_platforms": "Uber Eats"', payload)
            self.assertIn('"marketplace_providers": "Uber Eats"', payload)
            self.assertIn('"first_party_ordering": "ChowNow"', payload)


if __name__ == "__main__":
    unittest.main()
