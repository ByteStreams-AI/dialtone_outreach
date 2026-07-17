-- Migration: 003_add_website_url
-- Created: 2026-07-17
-- Description: Add website_url column to leads for direct linking during sales research

ALTER TABLE leads
    ADD COLUMN IF NOT EXISTS website_url TEXT;
