from pathlib import Path


MIGRATION = (
    Path(__file__).parents[1] / "db" / "migrations" / "009_add_contact_phone.sql"
).read_text(encoding="utf-8")


def test_contact_phone_migration_adds_nullable_column_idempotently() -> None:
    assert "ADD COLUMN IF NOT EXISTS contact_phone VARCHAR(50)" in MIGRATION
    assert "NOT NULL" not in MIGRATION
