-- Migration: 009_add_contact_phone
-- Created: 2026-07-28
-- Description: Add an editable contact phone number to CRM leads

ALTER TABLE leads
    ADD COLUMN IF NOT EXISTS contact_phone VARCHAR(50);