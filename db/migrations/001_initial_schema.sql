-- Migration: 001_initial_schema
-- Created: 2026-07-17
-- Description: Create leads, sales_users, and interactions tables

-- ── Extensions ────────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS moddatetime;

-- ── leads ─────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS leads (
    lead_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identity
    business_name        VARCHAR(255) NOT NULL,
    contact_name         VARCHAR(255),
    phone                VARCHAR(50),
    email                VARCHAR(255),
    address              TEXT,
    city                 VARCHAR(100),

    -- Scrape provenance
    source_url           TEXT,
    scrape_source        VARCHAR(50),

    -- Status
    status               VARCHAR(50) NOT NULL DEFAULT 'new'
                         CHECK (status IN (
                             'new', 'contacted', 'followup_required',
                             'demo_scheduled', 'closed_won', 'closed_lost'
                         )),

    -- Operational attributes
    business_type        VARCHAR(50)
                         CHECK (business_type IN (
                             'food_truck', 'single_location',
                             'multi_location', 'enterprise'
                         )),
    num_locations        INT,
    has_website          BOOLEAN DEFAULT FALSE,
    has_app              BOOLEAN DEFAULT FALSE,
    offers_delivery      BOOLEAN DEFAULT FALSE,
    offers_pickup        BOOLEAN DEFAULT FALSE,
    delivery_platforms   TEXT,
    uses_doordash_mktg   BOOLEAN DEFAULT FALSE,
    uses_chownow         BOOLEAN DEFAULT FALSE,
    uses_pos             VARCHAR(100),
    uses_kds             BOOLEAN DEFAULT FALSE,
    uses_sms             BOOLEAN DEFAULT FALSE,

    notes                TEXT,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (phone),
    UNIQUE (business_name, city)
);

CREATE TRIGGER leads_updated_at
    BEFORE UPDATE ON leads
    FOR EACH ROW EXECUTE PROCEDURE moddatetime(updated_at);

-- ── sales_users ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS sales_users (
    salesperson_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    name            VARCHAR(255) NOT NULL,
    role            VARCHAR(50) CHECK (role IN ('founder', 'sales', 'support')),
    active          BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── interactions ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS interactions (
    interaction_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id           UUID NOT NULL REFERENCES leads(lead_id) ON DELETE CASCADE,
    salesperson_id    UUID REFERENCES sales_users(salesperson_id) ON DELETE SET NULL,

    interaction_date  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    interaction_type  VARCHAR(50) NOT NULL
                      CHECK (interaction_type IN (
                          'phone_call', 'sms', 'email', 'in_person',
                          'demo', 'followup', 'info_sent'
                      )),

    requires_followup BOOLEAN DEFAULT FALSE,
    sent_info         BOOLEAN DEFAULT FALSE,
    demo_date         TIMESTAMPTZ,

    notes             TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS interactions_lead_id_idx ON interactions (lead_id);
CREATE INDEX IF NOT EXISTS interactions_date_idx    ON interactions (interaction_date DESC);

-- ── Row Level Security ────────────────────────────────────────────────────────
ALTER TABLE leads        ENABLE ROW LEVEL SECURITY;
ALTER TABLE interactions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "leads_read"  ON leads FOR SELECT USING (auth.role() = 'authenticated');
CREATE POLICY "leads_write" ON leads FOR ALL    USING (auth.role() = 'authenticated');

CREATE POLICY "interactions_read"  ON interactions FOR SELECT USING (auth.role() = 'authenticated');
CREATE POLICY "interactions_write" ON interactions FOR ALL    USING (auth.role() = 'authenticated');
