-- Migration: 007_add_lead_change_actor_email
-- Created: 2026-07-26
-- Description: Record a searchable email address for the user who changed a lead

ALTER TABLE lead_change_log
    ADD COLUMN IF NOT EXISTS changed_by_email TEXT;

CREATE INDEX IF NOT EXISTS lead_change_log_changed_by_email_idx
    ON lead_change_log (changed_by_email);

CREATE OR REPLACE FUNCTION capture_lead_change()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    request_headers JSONB := COALESCE(
        NULLIF(current_setting('request.headers', TRUE), '')::JSONB,
        '{}'::JSONB
    );
    jwt_claims JSONB := COALESCE(
        NULLIF(current_setting('request.jwt.claims', TRUE), '')::JSONB,
        '{}'::JSONB
    );
    actor_email TEXT := COALESCE(
        jwt_claims ->> 'email',
        request_headers ->> 'x-actor-email'
    );
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO lead_change_log (
            lead_id, operation, new_record, changed_by, changed_by_email
        ) VALUES (
            NEW.lead_id, TG_OP, to_jsonb(NEW), auth.uid(), actor_email
        );
        RETURN NEW;
    ELSIF TG_OP = 'UPDATE' THEN
        INSERT INTO lead_change_log (
            lead_id, operation, old_record, new_record, changed_by, changed_by_email
        ) VALUES (
            NEW.lead_id, TG_OP, to_jsonb(OLD), to_jsonb(NEW), auth.uid(), actor_email
        );
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        INSERT INTO lead_change_log (
            lead_id, operation, old_record, changed_by, changed_by_email
        ) VALUES (
            OLD.lead_id, TG_OP, to_jsonb(OLD), auth.uid(), actor_email
        );
        RETURN OLD;
    END IF;

    RAISE EXCEPTION 'Unsupported operation: %', TG_OP;
END;
$$;