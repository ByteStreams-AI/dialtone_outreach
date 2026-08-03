-- Migration: 010_add_ordering_provider_fields
-- Created: 2026-08-02
-- Description: Replace boolean ordering flags with structured provider text fields

ALTER TABLE leads
    ADD COLUMN IF NOT EXISTS marketplace_providers  TEXT,
    ADD COLUMN IF NOT EXISTS first_party_ordering   TEXT;

-- Drop the narrow boolean flags they replace
ALTER TABLE leads
    DROP COLUMN IF EXISTS uses_doordash_mktg,
    DROP COLUMN IF EXISTS uses_chownow;
