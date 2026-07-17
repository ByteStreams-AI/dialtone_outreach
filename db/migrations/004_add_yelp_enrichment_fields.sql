-- Migration: 004_add_yelp_enrichment_fields
-- Created: 2026-07-17
-- Description: Add price_range, yelp_rating, yelp_review_count from Yelp API

ALTER TABLE leads
    ADD COLUMN IF NOT EXISTS price_range        VARCHAR(10),
    ADD COLUMN IF NOT EXISTS yelp_rating        NUMERIC(3, 1),
    ADD COLUMN IF NOT EXISTS yelp_review_count  INT;
