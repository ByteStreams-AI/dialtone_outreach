"""Website-based detection of delivery marketplace and first-party ordering providers."""

from __future__ import annotations

import httpx
from bs4 import BeautifulSoup

# (url_substring, display_name) — matched against href/src/action attributes in page HTML.
# Marketplace: restaurants pay 15-30% commission and lose customer data.
_MARKETPLACE: list[tuple[str, str]] = [
    ("doordash.com/store", "DoorDash"),
    ("doordash.com/menu", "DoorDash"),
    ("ubereats.com/store", "Uber Eats"),
    ("ubereats.com/menu", "Uber Eats"),
    ("grubhub.com/restaurant", "Grubhub"),
    ("grubhub.com/place", "Grubhub"),
    ("seamless.com/menu", "Seamless"),
    ("postmates.com/merchant", "Postmates"),
]

# First-party: restaurant owns the ordering relationship directly.
_FIRST_PARTY: list[tuple[str, str]] = [
    ("ordering.chownow.com", "ChowNow"),
    ("cdn.chownow.com", "ChowNow"),
    ("order.chownow.com", "ChowNow"),
    ("order.toasttab.com", "Toast Online"),
    ("squareup.com/store", "Square Online"),
    ("square.site", "Square Online"),
    ("my.olo.com", "Olo"),
    ("oloorder.com", "Olo"),
    ("slicelife.com/restaurants", "Slice"),
    ("bopple.com", "Bopple"),
    ("flipdish.com", "Flipdish"),
]

_SCAN_ATTRS = ("href", "src", "data-src", "action")


def _scan_html(html: str) -> tuple[list[str], list[str]]:
    soup = BeautifulSoup(html, "lxml")
    all_urls: list[str] = []
    for tag in soup.find_all(True):
        for attr in _SCAN_ATTRS:
            val = tag.get(attr, "")
            if val:
                all_urls.append(val.lower())

    found_marketplace: list[str] = []
    found_first_party: list[str] = []
    seen: set[str] = set()

    for url in all_urls:
        for pattern, name in _MARKETPLACE:
            if pattern in url and name not in seen:
                found_marketplace.append(name)
                seen.add(name)
        for pattern, name in _FIRST_PARTY:
            if pattern in url and name not in seen:
                found_first_party.append(name)
                seen.add(name)

    return found_marketplace, found_first_party


def detect_providers(
    website_url: str,
    client: httpx.Client,
) -> tuple[list[str], list[str]]:
    """Fetch website_url and return (marketplace_providers, first_party_providers).

    Returns empty lists on any fetch or parse error — treat as unknown, not absent.
    """
    try:
        resp = client.get(website_url, timeout=10.0, follow_redirects=True)
        resp.raise_for_status()
        return _scan_html(resp.text)
    except Exception:
        return [], []
