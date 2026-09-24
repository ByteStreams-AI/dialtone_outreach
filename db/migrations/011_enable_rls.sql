-- Migration: 011_enable_rls
-- Created: 2026-09-22
-- Description: Enable RLS on sales_users — Supabase flagged it CRITICAL
--              `rls_disabled_in_public`.
--
-- The alert said "Anyone with your project URL can read, edit, and delete all
-- data in this table because Row-Level Security is not enabled", and that was
-- accurate: RLS was off AND all seven privileges were granted to both `anon`
-- and `authenticated`, so the anon key alone was read/write/DELETE on a table
-- of user records.
--
-- NO POLICY IS ADDED, deliberately. Everything that touches this table reaches
-- Supabase with the service key (scraper/db.py, SUPABASE_SERVICE_KEY), which
-- bypasses RLS — so denying anon and authenticated removes nothing that works
-- today. If a browser surface is ever built on this, it needs policies written
-- for it at that point; inheriting a wide-open table instead is how this
-- happened.
--
-- The REVOKE is not redundant with RLS. Supabase's default ACL grants
-- anon/authenticated on every new table, and `revoke ... from public` alone
-- does not remove those, so both statements are needed.
--
-- This project is SHARED: the social tables carrying the same alert belong to
-- dialtone_social (migrations/017_enable_rls.sql). Both must be run before the
-- alert clears.

BEGIN;

ALTER TABLE public.sales_users ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.sales_users FROM public, anon, authenticated;

COMMIT;

-- Verify (expect zero rows):
--   select c.relname
--   from pg_class c join pg_namespace n on n.oid = c.relnamespace
--   where n.nspname = 'public' and c.relkind in ('r','p') and not c.relrowsecurity;
