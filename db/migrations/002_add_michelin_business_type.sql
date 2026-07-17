-- Migration: 002_add_michelin_business_type
-- Created: 2026-07-17
-- Description: Add multi_configuration to business_type CHECK; add michelin_rating column

-- ── business_type: add multi_configuration ────────────────────────────────────
ALTER TABLE leads
    DROP CONSTRAINT IF EXISTS leads_business_type_check;

ALTER TABLE leads
    ADD CONSTRAINT leads_business_type_check
    CHECK (business_type IN (
        'food_truck',
        'single_location',
        'multi_configuration',
        'multi_location',
        'enterprise'
    ));

-- ── michelin_rating ───────────────────────────────────────────────────────────
ALTER TABLE leads
    ADD COLUMN IF NOT EXISTS michelin_rating VARCHAR(50)
    CHECK (michelin_rating IN (
        '1_star',
        '2_stars',
        '3_stars',
        'bib_gourmand',
        'green_star'
    ));
