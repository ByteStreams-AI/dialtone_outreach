# Developer Journal — Lead Discovery Scraper

**Purpose:** Running log of significant project events — bug fixes, feature implementations, and scope changes.

---

## Entry Format

```
### YYYY-MM-DD — [Bug Fix | Feature | Scope Change | Code Review | Infrastructure | Documentation] — Short Title
**Phase:** <current phase>
**Files Changed:** <key files affected>
**Summary:** <what changed and why>
**Notes:** <optional — gotchas, follow-ups, decisions made>
```

## Entry Placement

- Entries should be added at the top. Oldest at the bottom, latest at the top.

---

## Journal Entries

### 2026-07-28 — Feature — Add editable contact phone
**Phase:** CRM usability
**Files Changed:** db/migrations/009_add_contact_phone.sql, docs/CRM-SQL-Schema.md, bytestreams_info CRM types, data access, route, and view
**Summary:** Added nullable `contact_phone` storage and exposed it as an editable, normalized, click-to-dial field in the CRM lead table and forms.

### 2026-07-28 — Feature — Add dialable lead phone URIs
**Phase:** CRM usability
**Files Changed:** cli.py, db/migrations/008_normalize_lead_phone_tel_uri.sql, tests/test_phone_normalization.py
**Summary:** Normalized scraped and manually entered phone numbers to `tel:` URIs, using E.164 for US and explicitly international numbers and digit-only local URIs otherwise. Added a guarded data migration for existing Supabase leads.
**Notes:** The migration aborts if multiple legacy values normalize to the same unique phone number so those duplicate leads can be reviewed before retrying.

### 2026-07-26 — Feature — Add readable CDC actor email
**Phase:** Data integrity
**Files Changed:** db/migrations/007_add_lead_change_actor_email.sql, tests/test_lead_change_log_migration.py
**Summary:** Extended lead change events with `changed_by_email`. The trigger prefers authenticated Supabase JWT email claims and falls back to a trusted server request header for Cloudflare Access users.
**Notes:** Existing events cannot be backfilled reliably. Scraper and other service-role changes without a user email remain identifiable as service operations.

### 2026-07-26 — Feature — Add lead change data capture
**Phase:** Data integrity
**Files Changed:** db/migrations/006_add_lead_change_log.sql, tests/test_lead_change_log_migration.py
**Summary:** Added trigger-based CDC for the `leads` table. Every insert, update, and delete now produces a durable JSONB audit event containing old/new row snapshots, the Supabase actor when available, timestamp, and PostgreSQL transaction ID.
**Notes:** The audit table has RLS enabled, is readable by authenticated users, and rejects direct inserts, updates, deletes, and truncation from application roles. Delete events intentionally retain `lead_id` without a foreign key so their history survives removal of the source row.

### 2026-07-26 — Bug Fix — Preserve curated leads during city re-scrapes
**Phase:** Data integrity
**Files Changed:** scraper/db.py, tests/test_db.py
**Summary:** Changed Yelp scrape conflict handling to ignore existing `(business_name, city)` rows instead of merging scrape data into them. This prevents `scrape-city` from overwriting curated CRM values and making updated leads disappear from filtered views. Added a regression test using ChopnBlok as the representative Houston lead.
**Notes:** Conditional enrichment still fills `business_type` and `website_url` only when those database fields are NULL. Live verification of the affected row was unavailable because Supabase credentials were not present in the shell.

### 2026-07-17 — Infrastructure — Migrated to uv project management
**Phase:** Developer experience
**Files Changed:** pyproject.toml, .python-version, docs/runbook.md, README.md, removed requirements.txt
**Summary:** Replaced manual venv + pip workflow with uv. Added build-system declaration so editable install and entry points work. Pinned Python to 3.12 in .python-version. Moved pytest to uv dev deps. Deleted requirements.txt — deps now live in pyproject.toml and uv.lock. Developers now run `uv sync` once and then `uv run python cli.py <cmd>` with no activation required.
**Notes:** 12/12 tests pass after migration. `uv run python cli.py status` confirmed working.

### 2026-07-16 — Feature — Houston Open Data adapter and CLI command
**Phase:** Feature implementation
**Files Changed:** scraper/fetch.py, scraper/houston.py, cli.py, tests/test_houston_adapter.py, scraper/export.py
**Summary:** Added JSON API support via `fetch_json()` and implemented a Houston-specific source adapter that pulls food establishment records from City of Houston open data, filters relevant establishment types, deduplicates by name, and maps records into `LeadItem`. Added `scrape-houston` command with `--limit`, `--offset`, and export options. Also fixed JSON export serialization for `HttpUrl` values by switching to `model_dump(mode="json")`.
**Notes:** Verified with tests: 12/12 passing.

### 2026-07-16 — Feature — Added call-prep fields for lead exports
**Phase:** Feature implementation
**Files Changed:** scraper/models.py, scraper/export.py, cli.py, tests/test_call_prep_fields.py
**Summary:** Extended the starter lead schema with boolean fields for website/app/pickup/delivery and platform notes, and updated CSV/JSON export plus CLI output so city-based lead lists can support call prep research.
**Notes:** This keeps the project lightweight while making the output more useful for restaurant and food-truck outreach. The runtime environment here is missing pip/pydantic, so full test execution was blocked until dependencies are available.

