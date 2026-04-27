-- ================================================================
-- DialTone Outreach — Supabase Schema
-- Run this in your Supabase SQL editor to set up the database.
-- ================================================================

-- ── contacts ─────────────────────────────────────────────────────
create table if not exists contacts (
  id                uuid primary key default gen_random_uuid(),

  -- Restaurant info (from Outscraper)
  restaurant_name   text,
  business_phone    text,
  website           text,
  restaurant_email  text,
  domain            text unique not null,   -- PRIMARY KEY for dedup & merge
  address           text,
  city              text,
  state             text,
  zip               text,
  rating            numeric(3,1),
  reviews           integer,
  category          text,

  -- Owner info (from Apollo, merged by domain)
  owner_first       text,
  owner_last        text,
  owner_email       text,
  owner_phone       text,
  title             text,

  -- Outreach state
  status            text not null default 'new',
  lead_score        integer check (lead_score between 1 and 5),
  notes             text,
  source            text,                   -- 'outscraper' | 'apollo' | 'manual'

  created_at        timestamptz default now(),
  updated_at        timestamptz default now()
);

-- Indexes for common query patterns
create index if not exists contacts_status_idx      on contacts (status);
create index if not exists contacts_domain_idx      on contacts (domain);
create index if not exists contacts_lead_score_idx  on contacts (lead_score desc);
create index if not exists contacts_owner_email_idx on contacts (owner_email);

-- ── email_log ─────────────────────────────────────────────────────
create table if not exists email_log (
  id               uuid primary key default gen_random_uuid(),
  contact_id       uuid not null references contacts (id) on delete cascade,
  sequence_number  integer not null check (sequence_number between 1 and 5),
  subject          text,
  message_id       text,          -- SES message ID for tracking
  sent_at          timestamptz default now(),
  opened_at        timestamptz,
  replied_at       timestamptz,
  error            text
);

create index if not exists email_log_contact_idx on email_log (contact_id);
create index if not exists email_log_sent_at_idx on email_log (sent_at desc);

-- ── View: contacts due for outreach ──────────────────────────────
-- Used by sequence.py — returns active contacts with an email address
-- ordered by lead_score so hottest leads go first.
create or replace view contacts_due_for_outreach as
select *
from contacts
where status not in (
    'demo_booked', 'pilot', 'customer',
    'not_interested', 'invalid', 'replied'
  )
  and owner_email is not null
  and owner_email <> ''
order by lead_score desc nulls last, created_at asc;

-- ── View: status counts for dashboard ────────────────────────────
create or replace view contact_status_counts as
select
  status,
  count(*)::integer as count
from contacts
group by status
order by count desc;

-- ── Row Level Security (optional but recommended) ─────────────────
-- Enable RLS and allow only the service role to read/write.
-- Uncomment if you want to lock down the tables:
--
-- alter table contacts  enable row level security;
-- alter table email_log enable row level security;
--
-- create policy "service role only" on contacts
--   using (auth.role() = 'service_role');
--
-- create policy "service role only" on email_log
--   using (auth.role() = 'service_role');

-- ── Trigger: auto-update updated_at ───────────────────────────────
create or replace function update_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

create trigger contacts_updated_at
  before update on contacts
  for each row execute function update_updated_at();
