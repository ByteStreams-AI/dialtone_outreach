-- Migration: 012_lock_crm_policies
-- Created: 2026-09-22
-- Description: Remove the permissive RLS policies exposing the CRM tables.
--
-- These tables had RLS ENABLED, so they were not in the Supabase CRITICAL
-- alert (011 covers those). Their POLICIES were the problem, and two of them
-- were worse than the alerted tables:
--
--   contacts   "dashboard read"  SELECT to {public} using (true)   273 rows
--   email_log  "dashboard read"  SELECT to {public} using (true)   685 rows
--
-- `to public` in Postgres means EVERY role, `anon` included, and `using (true)`
-- means every row. Combined with the table-level grants to anon, those two were
-- readable by anyone holding the project's anon key. No account needed.
--
-- The rest require an account but are still far wider than anything uses:
--
--   leads            _read  SELECT / _write ALL   auth.role() = 'authenticated'   3400 rows
--   interactions     _read  SELECT / _write ALL   auth.role() = 'authenticated'
--   lead_change_log  _read  SELECT                auth.role() = 'authenticated'
--
-- Note the two `_write` policies are cmd ALL: any authenticated user could
-- INSERT, UPDATE and DELETE every lead, not merely read them. If signup is
-- open on this project, "authenticated" means anyone who registers.
--
-- NOTHING IN THE BROWSER READS THESE. Verified rather than assumed:
--   * scraper/db.py uses SUPABASE_SERVICE_KEY (a CLI);
--   * the portal's CRM page loads leads in src/routes/crm/+page.server.ts via
--     $lib/server/supabase, and SvelteKit refuses to import $lib/server into
--     browser code. No .svelte file in that repo creates a Supabase client.
-- Service role bypasses RLS, so removing these policies removes nothing that
-- works today.
--
-- contacts and email_log have no identifiable owner in any repo — they appear
-- to predate the current tooling. Dropping a SELECT policy can only cause a
-- READ to fail, which is visible; leaving it is a standing exposure of names,
-- emails and message contents. If something does turn out to read them with
-- the anon key, it should be given a policy scoped to its actual need.

BEGIN;

DROP POLICY IF EXISTS "dashboard read"   ON public.contacts;
DROP POLICY IF EXISTS "dashboard read"   ON public.email_log;
DROP POLICY IF EXISTS leads_read         ON public.leads;
DROP POLICY IF EXISTS leads_write        ON public.leads;
DROP POLICY IF EXISTS interactions_read  ON public.interactions;
DROP POLICY IF EXISTS interactions_write ON public.interactions;
DROP POLICY IF EXISTS lead_change_log_read ON public.lead_change_log;

-- Defence in depth, same reasoning as 011: Supabase's default ACL grants
-- anon/authenticated on every new table and `revoke ... from public` alone
-- does not remove those.
REVOKE ALL ON
    public.contacts,
    public.email_log,
    public.leads,
    public.interactions,
    public.lead_change_log
  FROM public, anon, authenticated;

COMMIT;

-- Verify — expect zero rows:
--   select tablename, policyname, roles::text, qual
--   from pg_policies
--   where schemaname = 'public'
--     and tablename in ('contacts','email_log','leads','interactions','lead_change_log');
