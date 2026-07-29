import pytest

from cli import normalize_phone


@pytest.mark.parametrize(
    ("raw_phone", "expected"),
    [
        ("(713) 555-0101", "tel:+17135550101"),
        ("1-713-555-0101", "tel:+17135550101"),
        ("tel:+44 20 7946 0958", "tel:+442079460958"),
        ("0044 20 7946 0958", "tel:+442079460958"),
        ("555-0101", "tel:5550101"),
        (None, None),
        ("  ", None),
    ],
)
def test_normalize_phone(raw_phone: str | None, expected: str | None) -> None:
    assert normalize_phone(raw_phone) == expected


@pytest.mark.parametrize("raw_phone", ["12", "+0123456789", "not a number"])
def test_normalize_phone_rejects_invalid_values(raw_phone: str) -> None:
    with pytest.raises(ValueError, match="Invalid"):
        normalize_phone(raw_phone)
