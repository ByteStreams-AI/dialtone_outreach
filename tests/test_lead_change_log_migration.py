from pathlib import Path


MIGRATION = (
    Path(__file__).parents[1] / "db" / "migrations" / "006_add_lead_change_log.sql"
).read_text(encoding="utf-8")
ACTOR_EMAIL_MIGRATION = (
    Path(__file__).parents[1] / "db" / "migrations" / "007_add_lead_change_actor_email.sql"
).read_text(encoding="utf-8")


def test_lead_change_log_captures_all_operations() -> None:
    assert "AFTER INSERT OR UPDATE OR DELETE ON leads" in MIGRATION
    assert "to_jsonb(OLD)" in MIGRATION
    assert "to_jsonb(NEW)" in MIGRATION
    assert "auth.uid()" in MIGRATION
    assert "txid_current()" in MIGRATION


def test_lead_change_log_is_read_only_for_application_roles() -> None:
    assert "ALTER TABLE lead_change_log ENABLE ROW LEVEL SECURITY" in MIGRATION
    assert "FOR SELECT" in MIGRATION
    assert (
        "REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON lead_change_log FROM anon, authenticated"
        in MIGRATION
    )
    assert "GRANT SELECT ON lead_change_log TO authenticated" in MIGRATION


def test_actor_email_prefers_jwt_and_supports_server_attribution() -> None:
    assert "ADD COLUMN IF NOT EXISTS changed_by_email TEXT" in ACTOR_EMAIL_MIGRATION
    assert "jwt_claims ->> 'email'" in ACTOR_EMAIL_MIGRATION
    assert "request_headers ->> 'x-actor-email'" in ACTOR_EMAIL_MIGRATION
    assert "changed_by_email" in ACTOR_EMAIL_MIGRATION
