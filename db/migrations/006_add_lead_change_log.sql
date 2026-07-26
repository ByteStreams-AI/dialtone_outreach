-- Migration: 006_add_lead_change_log
-- Created: 2026-07-26
-- Description: Add a durable audit log for all changes to leads

CREATE TABLE IF NOT EXISTS lead_change_log (
    change_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id         UUID,
    operation       TEXT NOT NULL
                    CHECK (operation IN ('INSERT', 'UPDATE', 'DELETE')),
    old_record      JSONB,
    new_record      JSONB,
    changed_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    changed_by      UUID,
    transaction_id  BIGINT NOT NULL DEFAULT txid_current()
);

CREATE INDEX IF NOT EXISTS lead_change_log_lead_id_idx
    ON lead_change_log (lead_id);
CREATE INDEX IF NOT EXISTS lead_change_log_changed_at_idx
    ON lead_change_log (changed_at DESC);

CREATE OR REPLACE FUNCTION capture_lead_change()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO lead_change_log (
            lead_id, operation, new_record, changed_by
        ) VALUES (
            NEW.lead_id, TG_OP, to_jsonb(NEW), auth.uid()
        );
        RETURN NEW;
    ELSIF TG_OP = 'UPDATE' THEN
        INSERT INTO lead_change_log (
            lead_id, operation, old_record, new_record, changed_by
        ) VALUES (
            NEW.lead_id, TG_OP, to_jsonb(OLD), to_jsonb(NEW), auth.uid()
        );
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        INSERT INTO lead_change_log (
            lead_id, operation, old_record, changed_by
        ) VALUES (
            OLD.lead_id, TG_OP, to_jsonb(OLD), auth.uid()
        );
        RETURN OLD;
    END IF;

    RAISE EXCEPTION 'Unsupported operation: %', TG_OP;
END;
$$;

DROP TRIGGER IF EXISTS leads_change_audit ON leads;
CREATE TRIGGER leads_change_audit
    AFTER INSERT OR UPDATE OR DELETE ON leads
    FOR EACH ROW EXECUTE FUNCTION capture_lead_change();

ALTER TABLE lead_change_log ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS lead_change_log_read ON lead_change_log;
CREATE POLICY lead_change_log_read
    ON lead_change_log
    FOR SELECT
    USING (auth.role() = 'authenticated');

REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON lead_change_log FROM anon, authenticated;
GRANT SELECT ON lead_change_log TO authenticated;
