# CRM SQL Schema

## Overview

Five tables. Create in this order to satisfy foreign key dependencies:
`leads` → `sales_users` → `interactions`

Status is a CHECK constraint on `leads` directly — no lookup table needed for a fixed seven-value enum.
Operational attributes are merged into `leads` to avoid a join on every query.
`sales_users` links to Supabase `auth.users` so no parallel user store is needed.

---

## Enable required extensions

```sql
-- UUID generation and auto-updated timestamps
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS moddatetime;
```

---

## Table: leads

Core identity, status, and all operational attributes for a prospect.

```sql
CREATE TABLE leads (
    lead_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identity
    business_name        VARCHAR(255) NOT NULL,
    contact_name         VARCHAR(255),
    contact_phone        VARCHAR(50),
    phone                VARCHAR(50),
    email                VARCHAR(255),
    address              TEXT,
    city                 VARCHAR(100),

    -- Scrape provenance
    source_url           TEXT,           -- Yelp or other scrape origin
    scrape_source        VARCHAR(50),    -- e.g. 'yelp', 'manual'

    -- Lead status
    status               VARCHAR(50) NOT NULL DEFAULT 'new'
                         CHECK (status IN (
                             'new', 'contacted', 'followup_required',
                             'demo_scheduled', 'closed_won', 'closed_lost'
                         )),

    -- Operational attributes (formerly lead_attributes)
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
    delivery_platforms   TEXT,           -- e.g. 'doordash,ubereats'
    uses_doordash_mktg   BOOLEAN DEFAULT FALSE,
    uses_chownow         BOOLEAN DEFAULT FALSE,
    uses_pos             VARCHAR(100),
    uses_kds             BOOLEAN DEFAULT FALSE,
    uses_sms             BOOLEAN DEFAULT FALSE,

    notes                TEXT,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Prevent duplicate imports
    UNIQUE (phone),
    UNIQUE (business_name, city)
);

-- Auto-update updated_at on every row change
CREATE TRIGGER leads_updated_at
    BEFORE UPDATE ON leads
    FOR EACH ROW EXECUTE PROCEDURE moddatetime(updated_at);
```

---

## Table: sales_users

Internal team members. Linked to Supabase auth so no separate password management.

```sql
CREATE TABLE sales_users (
    salesperson_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    name            VARCHAR(255) NOT NULL,
    role            VARCHAR(50) CHECK (role IN ('founder', 'sales', 'support')),
    active          BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

## Table: interactions

Every touchpoint — calls, texts, demos, follow-ups.

```sql
CREATE TABLE interactions (
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

    -- Demo fields: non-null date means demo is scheduled
    demo_date         TIMESTAMPTZ,

    notes             TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX interactions_lead_id_idx ON interactions (lead_id);
CREATE INDEX interactions_date_idx    ON interactions (interaction_date DESC);
```

---

## Relationship Summary

| Relationship               | Type |
| -------------------------- | ---- |
| leads → interactions       | 1:M  |
| sales_users → interactions | 1:M  |
| auth.users → sales_users   | 1:1  |

---

## Row Level Security (Supabase)

Enable RLS so authenticated reps only see active data. Adjust policies to your access model.

```sql
ALTER TABLE leads        ENABLE ROW LEVEL SECURITY;
ALTER TABLE interactions ENABLE ROW LEVEL SECURITY;

-- Example: all authenticated users can read leads
CREATE POLICY "leads_read" ON leads
    FOR SELECT USING (auth.role() = 'authenticated');

-- Example: reps can insert/update leads they own
CREATE POLICY "leads_write" ON leads
    FOR ALL USING (auth.role() = 'authenticated');
```

---

## Useful Queries

### Leads requiring follow-up

```sql
SELECT l.lead_id, l.business_name, l.phone, i.interaction_date
FROM leads l
JOIN interactions i ON l.lead_id = i.lead_id
WHERE i.requires_followup = TRUE
ORDER BY i.interaction_date DESC;
```

### Food trucks contacted by founder

```sql
SELECT l.business_name, i.interaction_date, i.interaction_type
FROM leads l
JOIN interactions i ON l.lead_id = i.lead_id
JOIN sales_users s ON i.salesperson_id = s.salesperson_id
WHERE l.business_type = 'food_truck'
  AND s.role = 'founder'
ORDER BY i.interaction_date DESC;
```

### Leads with demos scheduled

```sql
SELECT l.business_name, l.phone, i.demo_date
FROM leads l
JOIN interactions i ON l.lead_id = i.lead_id
WHERE i.demo_date IS NOT NULL
ORDER BY i.demo_date ASC;
```

### Pipeline summary by status

```sql
SELECT status, COUNT(*) AS count
FROM leads
GROUP BY status
ORDER BY count DESC;
```
