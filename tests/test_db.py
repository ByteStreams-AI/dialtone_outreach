from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from scraper.db import _filter_conflicting_rows, upsert_leads
from scraper.models import LeadItem


def _row(name: str, city: str, phone: str | None) -> dict:
    return {"business_name": name, "city": city, "phone": phone}


def test_filter_keeps_phone_owned_by_same_lead() -> None:
    row = _row("Existing Restaurant", "Chicago", "(312) 733-4818")

    filtered, skipped = _filter_conflicting_rows([row], [row])

    assert filtered == [row]
    assert skipped == 0


def test_filter_drops_phone_owned_by_different_lead() -> None:
    scraped = _row("New Restaurant", "Chicago", "(312) 733-4818")
    existing = _row("Existing Restaurant", "Chicago", "(312) 733-4818")

    filtered, skipped = _filter_conflicting_rows([scraped], [existing])

    assert filtered == []
    assert skipped == 1


def test_filter_deduplicates_batch_by_phone_and_identity() -> None:
    first = _row("Restaurant", "Chicago", "(312) 555-0100")
    duplicate_phone = _row("Other Name", "Chicago", "(312) 555-0100")
    duplicate_identity = _row("Restaurant", "Chicago", "(312) 555-0199")
    no_phone = _row("No Phone", "Chicago", None)

    filtered, skipped = _filter_conflicting_rows(
        [first, duplicate_phone, duplicate_identity, no_phone], []
    )

    assert filtered == [first, no_phone]
    assert skipped == 2


def test_upsert_preserves_existing_lead_on_identity_conflict() -> None:
    lead = LeadItem(
        name="ChopnBlok",
        source="https://api.yelp.com/v3/businesses/search",
        url="https://www.yelp.com/biz/chopnblok-houston",
        city="Houston",
        phone="(832) 962-4500",
    )
    table = MagicMock()
    table.select.return_value.in_.return_value.execute.return_value = SimpleNamespace(data=[])
    table.upsert.return_value.execute.return_value = SimpleNamespace(data=[{"lead_id": "new"}])
    client = MagicMock()
    client.table.return_value = table

    with patch("scraper.db._get_client", return_value=client):
        upsert_leads([lead])

    table.upsert.assert_called_once()
    assert table.upsert.call_args.kwargs == {
        "on_conflict": "business_name,city",
        "ignore_duplicates": True,
    }
