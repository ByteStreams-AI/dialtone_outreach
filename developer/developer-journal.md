# Developer Journal — DialTone Outreach

**Purpose:** Running log of significant project events — bug fixes, feature implementations, and scope changes. Updated as work progresses through each phase.

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

- Entries should be added at the top

---

## Journal Entries

### 2026-05-01 — Feature — Milestone 4: Local Web UI v1

**Phase:** Milestone 4 — Local Web UI v1.

**Files Changed:**

- `web/__init__.py` (new) — package marker.
- `web/app.py` (new) — FastAPI app with 7 routes: dashboard (`/`), contacts list (`/contacts`), HTMX partial (`/partials/contacts`), contact detail (`/contacts/{id}`), status update POST, notes update POST, run preview (`/run-preview`).
- `web/templates/base.html` (new) — layout with nav (Dashboard | Contacts | Run Preview), Pico CSS CDN, HTMX CDN.
- `web/templates/dashboard.html` (new) — status counts table, conversion funnel, emails sent today.
- `web/templates/contacts.html` (new) — search + filter form with HTMX-driven partial updates.
- `web/templates/partials/contact_rows.html` (new) — HTMX partial for contacts table `<tbody>`.
- `web/templates/contact_detail.html` (new) — owner info, email history, status buttons, notes editor.
- `web/templates/run_preview.html` (new) — read-only dry-run table.
- `web/static/style.css` (new) — status badges, filter bar, nav active states on Pico CSS.
- `outreach/db.py` — new `search_contacts()` (multi-field filter with `or_` for free-text) and `update_contact_notes()`.
- `requirements.txt` — added `fastapi==0.115.0`, `uvicorn[standard]==0.32.0`, `python-multipart==0.0.20`.
- `AGENTS.md` — repo layout updated with `web/` entries, stack description updated.
- `docs/project-status.md` — all M4 steps ticked, milestone marked complete.
- `docs/web-ui-guide.md` (new) — user guide for non-technical reviewers.

**Summary:** Built a local FastAPI + Jinja2 + HTMX web UI for non-technical reviewers to monitor outreach and update contact statuses without touching the CLI or Supabase. Four screens: Dashboard (status counts, conversion funnel, emails today), Contacts (search/filter with HTMX partials), Contact Detail (status edit buttons, email history, notes), Run Preview (dry-run view). Reuses `outreach/db.py` and `outreach/sequence.py` directly — no duplicated business logic. Styled with Pico CSS (CDN) + custom overrides. No build step, no auth (local-only by design). Sending is not exposed.

**Bug fixes during development:**

- HTMX CDN URL `https://unpkg.com/htmx.org@1.9.12` returns a 301 redirect; some browsers block redirecting script sources. Fixed by using the full path `.../dist/htmx.min.js`.
- HTMX `hx-trigger` with `from:` selectors on a parent form was unreliable for bubbled events. Fixed by moving `hx-get`/`hx-trigger`/`hx-include` to each individual input/select.
- FastAPI `Optional[int]` query param rejects empty strings (`score=`) with 422. Fixed by accepting `Optional[str]` and parsing with `_parse_score()`.

---

### 2026-05-01 — Feature — Milestone 3: Reply Detection Automation (IMAP Polling)

**Phase:** Milestone 3 — Reply Detection Automation.

**Files Changed:**

- `outreach/reply_checker.py` (new) — IMAP-based reply scanner. Connects to the reply mailbox, searches UNSEEN messages, matches senders against `contacts.owner_email`, and marks matched contacts + email_log rows as replied. Messages from known contacts are marked SEEN in IMAP after processing.
- `outreach/audit.py` (new) — Status-mismatch detector. `run_audit()` finds contacts where `email_log.replied_at` is set but `contacts.status` is not terminal, and optionally fixes them.
- `outreach/config.py` — New env vars: `REPLY_CHECK_IMAP_HOST`, `REPLY_CHECK_IMAP_PORT`, `REPLY_CHECK_EMAIL`, `REPLY_CHECK_PASSWORD`.
- `outreach/db.py` — New helpers: `find_contact_by_owner_email()` (case-insensitive ILIKE lookup), `find_reply_status_mismatches()` (cross-table audit query).
- `cli.py` — New `check-replies` command with `--dry-run`, `--audit`, and `--fix` flags.
- `.env.example` — Documented all `REPLY_CHECK_*` env vars with Gmail App Password instructions.
- `README.md` — Replaced placeholder "Connecting Reply Detection" section with full IMAP setup + cron instructions + M6 scheduling note. Added env vars to reference table.
- `AGENTS.md` — Added `check-replies` to CLI cheatsheet.
- `docs/project-status.md` — Ticked M3 implementation steps, documented mechanism decision, added M6 scheduling pivot note.

**Summary:** Implemented IMAP-based reply detection as a CLI command (`python cli.py check-replies`). The mechanism was chosen over SES+SNS+Lambda because it requires no infrastructure changes (no MX records, no Lambda deployment), uses only Python stdlib (`imaplib`, `email`), and works with any mail provider. Automated scheduling is deferred to M6 — during the pilot phase, the operator runs `check-replies` manually before each cohort send. The audit command (`--audit [--fix]`) acts as a safety net for partial failures or manual Supabase edits that leave the two tables out of sync.

**Notes:**

- No new dependencies. `imaplib` and `email` are Python stdlib.
- **Live test passed 2026-05-01.** Inserted a test contact with `owner_email=cottonbytes@gmail.com`, sent via `send-test`, replied from Gmail, ran `check-replies`: `Scanned: 1, Matched: 1`. Contact status flipped to `replied`, `email_log.replied_at` set on the most recent log row.
- Bug fix during testing: the original `conn.fetch(uid, "(RFC822)")` implicitly marks messages as `\Seen` in IMAP, so unmatched messages disappeared on the next run. Switched to `BODY.PEEK[]` which fetches without setting the flag — only explicitly matched messages are marked SEEN now.
- Scheduling was explicitly deferred to M6. The `check-replies` command is a standard CLI entry point, so it slots into whatever scheduling infrastructure M6 provisions (cron on EC2, EventBridge + Lambda, etc.) without code changes.

---

### 2026-04-30 — Feature — First Live Cohort Sent (`batch-1`, 5 contacts)

**Phase:** Milestone 2 step 5 — first live send. Warmup day 0.

**Files Changed:** None (operational). Database state changed: 5 contacts moved `new` → `emailed_1`; 5 corresponding rows inserted into `email_log` with non-null `message_id`s.

**Summary:** First production cold-email cohort shipped through SES. Sequence executed by `python cli.py run --cohort batch-1` against a locked, reviewer-approved contact set. SES quota: 50,000/24h (production access), warmup limit: 5/day on day 0. Send result: `Sent: 5, Skipped: 0, Errors: 0`. No SES-side errors at the API layer; bounce / complaint signals come back asynchronously over the next 24–72h via the SES Console reputation tab (SNS topic wiring is optional and may land with M3).

**Final cohort (`developer/cohorts/batch-1.json`, gitignored):**

1. Hattie B's Hot Chicken — `joem@hattieb.com` — Nashville, TN.
2. Stoney River Steakhouse and Grill — `cboyd@stoneyriver.com` — Nashville, TN. (Regional ~11-location group; user-approved as borderline.)
3. Bluff City Crab — `jason@bluffcitycrab.com` — Memphis, TN.
4. Party Fowl — `chris@partyfowl.com` — Nashville, TN.
5. Newk's Eatery — `mduncan@newks.com` — Jackson. (Regional ~110-location group; user-approved as borderline.)

**Reviewer cleanup that landed during cohort iteration:**

Marked terminal in `contacts` (so they never re-enter the cohort pool):

- `greenhillsbarbershop.com` — `invalid` (not a restaurant).
- `insomniacookies.com` — `not_interested` (national chain).
- `firehouse subs` — `not_interested` (caught by chain regex, ~1,200 locations).
- `juneshine.co` — `invalid` (beverage brand, not a restaurant). Required updating by `owner_email` ILIKE because the stored `domain` was `.com`, not `.co`.
- `spbhospitality.com` — `not_interested` (multi-brand operator, owns Stoney River et al).
- A regex sweep over `restaurant_name` for `(barber\|salon\|spa\|clinic\|...)` and a separate sweep for `(brands\|hospitality group\|holdings\|management\|group$\|enterprises)` to catch the long tail of non-restaurants and holding/management entities.

**Notes:**

- The cohort lock was iterated several times because Apollo's "Industry: Restaurants" filter is leaky — about 40% of the top picks were either non-restaurants (kombucha brand, barber shop) or large national chains (Firehouse, Insomnia). Worth a future M5-side hardening: lift `is_chain()` and a non-restaurant keyword filter into Apollo's branch of `passes_quality_filter`. Until then, periodic SQL sweeps before each cohort lock are the operator workflow.
- The `domain` mismatch on JuneShine (Apollo CSV had `juneshine.com` website + `forrest@juneshine.co` email; importer stored `juneshine.com` as the domain) is a one-off but worth remembering: when targeting a contact for cleanup, use `owner_email` rather than `domain` to avoid this class of miss.
- M2 step 6 (7-day metrics review) opens automatically: `python cli.py metrics --cohort batch-1` will be the gate. Acceptance thresholds: bounce < 5%, complaint < 0.1%, ≥1 real reply.
- Sender identity used: `hello@dialtone.menu` (verified email-address identity, also covered by the verified `dialtone.menu` domain identity for DKIM).
- Tomorrow (warmup day 1): another 5-email cohort. The runner will skip the 5 contacts in `emailed_1` until day-3 of their personal sequence; the cohort pool is still ~266 active `new` contacts.

---

### 2026-04-30 — Bug Fix — Apollo Import Rejected Every Row (`# Employees` schema-cache error)

**Phase:** Milestone 2 step 4 (cohort lock prep). First live import attempt against the populated Supabase schema produced 0 imported, 107 skipped, **271 errors** — every Apollo row failed.

**Files Changed:**

- `scripts/import_contacts.py` — added `CONTACT_COLUMNS` allowlist (frozenset of every column that exists on the `contacts` table per `schema.sql`); the upsert loop now filters each record dict through that allowlist before calling `upsert_contact()`.
- `AGENTS.md` — added a "Contact column allowlist" bullet to the coding-conventions section so future schema changes also touch `CONTACT_COLUMNS`.
- `developer/developer-journal.md` — this entry.

**Summary:** Apollo CSVs ship with columns the `contacts` table doesn't have (`# Employees`, `Industry`, `Annual Revenue`, `Stage`, `Lists`, `Person Linkedin Url`, etc.). The original importer built the upsert payload from `row.to_dict().items()` directly, which forwarded every Apollo column to PostgREST. Supabase rejected each row with `Could not find the '<X>' column of 'contacts' in the schema cache`. The fix is a single allowlist filter applied just before the upsert; columns not in `CONTACT_COLUMNS` are silently dropped, which is exactly what the importer wants to do with metadata fields like `# Employees`.

**Notes:**

- After the fix, the expected import outcome on the sample CSV is roughly: ~271 imported, ~107 skipped (the PII-clean filter for `email status != valid` or empty `owner_email`), 0 errors.
- `CONTACT_COLUMNS` is now an invariant: schema migrations must add to it, schema removals must remove from it. Documented in `AGENTS.md` so future agents catch this.
- The 107 skipped rows are deliberate — see `passes_quality_filter()` in the same file. Skipping `email status ≠ valid` rows is a Milestone 1 deliverability decision, not a regression.
- Generic in scope: any future Apollo export with new columns Apollo decides to ship will be tolerated automatically because the allowlist is anchored to the schema, not the CSV.

---

### 2026-04-30 — Feature — Milestone 2 Tooling (First Live Cohort)

**Phase:** Repo-side implementation of Milestone 2 (`First Live Cohort`). Operator-only steps (SES sandbox exit, DNS, executing the live send, 7-day wait) remain pending and are documented in the new runbook.

**Files Changed:**

- `outreach/config.py` — new `WARMUP_START_DATE` and `WARMUP_DAY_LIMITS` env vars, plus `effective_send_limit(today=None)` that maps a date to the right cap.
- `outreach/preflight.py` (new) — Rich-table go/no-go report covering env, Supabase connectivity, SES quota / sandbox / sender identity / DKIM, and SPF / DMARC TXT records (uses `dnspython` if installed, otherwise yields ``skip`` rows).
- `outreach/cohort.py` (new) — JSON-backed cohort lock under `developer/cohorts/<slug>.json`. `lock_cohort`, `load_cohort`, `unlock_cohort`, `list_cohorts`, plus a `Cohort` dataclass with the contact_ids and a per-contact preview row.
- `outreach/metrics.py` (new) — `MetricsReport` dataclass + `report_window` / `report_cohort`. Renders bounce / complaint / reply / open / demo counts and grades them against the M2 acceptance thresholds (bounce <5%, complaint <0.1%, ≥1 reply).
- `outreach/db.py` — `mark_email_bounced`, `mark_email_complained`, and `get_email_log_metrics(since_iso, contact_ids)` aggregator.
- `outreach/runner.py` — reads from `effective_send_limit()` when `WARMUP_START_DATE` is set; new `--cohort` argument restricts the send to a locked cohort and respects cohort order; banner shows the limit source (`override` / `warmup` / `DAILY_SEND_LIMIT`).
- `cli.py` — new `preflight`, `cohort lock|show|unlock`, and `metrics` commands; existing `run` gains `--cohort`. `--cohort` and `--since` on `metrics` are mutually exclusive.
- `schema.sql` — idempotent migration adds `bounced_at`, `bounce_type`, `complained_at`, `complaint_type` columns plus matching indexes on `email_log`. Re-running the script is safe.
- `.env.example` — documents `WARMUP_START_DATE` and `WARMUP_DAY_LIMITS=5,5,5,10,10,10,20`.
- `.gitignore` — ignores `developer/cohorts/` (recipient PII).
- `README.md` — new "First Live Cohort (Milestone 2)" quick-reference section, env-var table extended, structure tree updated.
- `AGENTS.md` — CLI cheatsheet expanded; repo layout + runbook reference added.
- `docs/runbook-first-cohort.md` (new) — 8-step operator runbook for SES sandbox exit, DNS, warmup configuration, cohort lock + review, dry-run, live send, and 7-day metrics review.
- `docs/project-status.md` — each Milestone 2 step now annotates which CLI command provides code support and which parts remain operator-only.

**Summary:** Milestone 2 is mostly operational, but the repo previously had nothing to drive the operational work safely. This change lands the four pieces of repo-side tooling that enable a careful first cohort: (1) a `preflight` go/no-go gate, (2) a warmup-aware `run` so reviewers don't have to hand-edit `DAILY_SEND_LIMIT` between days, (3) JSON cohort locks so reviewers can sign off on a frozen contact list, and (4) a `metrics` command that grades the result against the published M2 thresholds. None of this performs the operator-only work itself — SES production-access, DNS edits, the live send, and the 7-day wait still happen outside the codebase per `docs/runbook-first-cohort.md`.

**Notes:**

- `dnspython` is treated as optional. If it isn't installed, `preflight` returns `skip` rows for SPF / DMARC and tells the operator to fall back to `dig`. This avoids forcing a new hard dependency on every environment that doesn't run the M2 flow.
- Cohort artifacts contain owner emails, which is why `developer/cohorts/` is gitignored. The `cohort show` table truncates subjects to 60 chars to keep the review surface narrow but readable.
- The `email_log` migration is idempotent (`alter table ... add column if not exists`). The user must re-run `schema.sql` against Supabase before the bounce / complaint columns become available; until then `metrics` will report zeroes for those counters.
- `metrics --cohort` and `metrics --since` are mutually exclusive by design — cohort metrics are scope-by-recipient (any time), time-window metrics are scope-by-send-time. Mixing them would be ambiguous.
- No tests yet (formal harness is M6); next-best smoke check is `python -c "import outreach, scripts"` plus `python scripts/preview_templates.py`. With a populated `.env`, `python cli.py preflight` and `python cli.py metrics --since 1d` exercise the new modules end to end.

---

### 2026-04-30 — Infrastructure — Address Milestone 1 Code Review Must-Fix Items

**Phase:** Pre-merge cleanup of `chore/email-gen-hardening` (PR #7), in response to the code-review entry below.

**Files Changed:**

- `.gitignore` (new) — Python boilerplate (`__pycache__/`, `*.py[cod]`, build artefacts, virtualenvs, test caches, editor / OS noise) plus project-specific exclusions: `.env` (with `!.env.example` allow-back), `logs/` + `*.log`, `apollo_export*.csv` PII guard, and `developer/template-previews/` to drop the regenerable preview artefacts.
- `.env.example` — Replaced placeholder `BUSINESS_ADDRESS` with the real ByteStreams mailing address: `"100 Powell Place #1473\nNashville, TN 37204\nUnited States"`. Quoted so `python-dotenv` parses the `\n` escapes into the multi-line address `_format_address_text()` / `_format_address_html()` expect.
- `README.md` — Same `BUSINESS_ADDRESS` example refresh in the `.env` snippet, plus structure tree updated to mark `developer/template-previews/` as gitignored and surface `developer/developer-journal.md`.
- `AGENTS.md` — Repo-layout block updated to mirror the README change (journal added, previews flagged as gitignored).
- `developer/developer-journal.md` — This entry.

**Summary:** Closes the three must-fix items called out in the prior review entry.

1. **`.gitignore` added.** Covers the standard Python + uv stack (`__pycache__/`, `*.py[cod]`, `build/`, `dist/`, `*.egg-info/`, `.venv/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `.coverage`, `htmlcov/`, etc.), secrets (`.env`, `.env.*` with `!.env.example`), runtime output (`logs/`, `*.log`), recipient PII (`apollo_export*.csv`), and editor / OS noise. Existing tracked caches still need a one-time `git rm -r --cached outreach/__pycache__ scripts/__pycache__` before they actually disappear from the index — left for the user to run per the no-stage/commit policy.
2. **`developer/template-previews/` gitignored.** Script `scripts/preview_templates.py` regenerates the 50-file 5×5 grid on demand, so committing them caused diff churn on every template tweak with no real review value. Same one-time `git rm -r --cached developer/template-previews/` is required to actually untrack them.
3. **`BUSINESS_ADDRESS` set to the real ByteStreams mailing address.** `100 Powell Place #1473, Nashville, TN 37204, United States`, encoded as a double-quoted, `\n`-separated value in `.env.example` and the README example block. The hard guard in `render_email()` only catches *unset*, but the example now ships a correct value so a fresh `cp .env.example .env` produces compliant output by default. Production `.env` should mirror this.

**Notes:**

- `git rm --cached` operations were intentionally **not** run — staging / committing on the user's behalf is out of policy. The user can drop the cache directories and previews from the index in a single follow-up commit when ready.
- Once the user re-runs `python scripts/preview_templates.py` the rendered HTML / text footers will contain the new address; the previously-tracked previews still show the old placeholder until then (and won't be regenerated into git after this change).
- Deferred should-fix items from the prior review remain deferred: Outscraper code paths (milestone 5), `UNSUBSCRIBE_URL` provisioning (config supports it, just not provisioned). README has been updated in earlier turns to document `send-test` and `preview_templates.py`, closing the third should-fix item.

---

### 2026-04-30 — Code Review — Milestone 1 (Email Generation Hardening) Completeness Review

**Phase:** Pre-merge review of `chore/email-gen-hardening` branch (PR #7)

**Files Reviewed:**

- `outreach/templates.py` — heavy refactor: new `clean_company_name()`, `_resolve_unsubscribe_url()`, `_text_footer()`, `_html_wrap()`, hardened `render_email()` with CAN-SPAM guards.
- `outreach/config.py` — new env vars: `BUSINESS_ADDRESS`, `COMPANY_LEGAL_NAME`, `UNSUBSCRIBE_EMAIL`, `UNSUBSCRIBE_URL`.
- `scripts/import_contacts.py` — Apollo column re-mapping to real headers (`company name`, `company city`, `company address`, `work direct phone`), Apollo `email status` filter, `clean_company_name()` applied at import time.
- `scripts/preview_templates.py` — new script: renders 5 contacts × 5 templates and writes both `.txt` and `.html` previews; includes Jinja-artifact regression check that exits non-zero on any leftover `{{ ... }}`.
- `cli.py` — new `send-test` subcommand with interactive confirmation prompt (`--yes` to skip).
- `.env.example` — documentation for the new CAN-SPAM env vars.
- `developer/template-previews/*` — 50 generated review artifacts (25 `.txt` + 25 `.html`).

**Summary:** Verified that all six milestone-1 steps are substantively complete on the `chore/email-gen-hardening` branch.

1. Unsubscribe-link rendering bug fixed — `_html_wrap()` now takes `unsubscribe_url` as a kwarg and inlines it via Python f-string, eliminating the `{{{{ unsubscribe_url }}}}` artifact that previously leaked literal Jinja syntax into recipient inboxes. A regex-based regression check in `preview_templates.py` enforces the fix going forward.
2. CAN-SPAM-compliant footer added in both text (`_text_footer`) and HTML (`_html_wrap`) variants, including sender identity, legal entity name, postal address, and a working unsubscribe link. `render_email()` raises `ValueError` if `BUSINESS_ADDRESS` is unset, making non-compliant sends impossible by accident.
3. Apollo CSV inspection drove a column re-map: outreach copy is now keyed off the *company* address (`company city`, `company state`, `company address`, `company phone`) rather than the owner's personal address, which is the correct lens for restaurant outreach. Bonus: rows whose Apollo `email status` is anything other than "valid" are dropped at import time — meaningful deliverability win for the first cohort.
4. Opener (`EMAIL_1_TEXT`) uses a `{% if city %}` Jinja hook so contacts with a city see a localized lede ("Quick question for Miami restaurant owners —…") and rows without one fall back cleanly to the original phrasing.
5. Fallback handling: `RESTAURANT_FALLBACK = "your restaurant"` and `FIRST_NAME_FALLBACK = "there"` cover empty / noisy Apollo rows. `clean_company_name()` strips trailing corporate suffixes (LLC, Inc., Corp., Ltd., Co., PLLC, PC, L.P.), surrounding quotes, and collapses whitespace; it runs at import time *and* at render time (idempotent), so legacy rows imported before the cleanup landed still render cleanly.
6. Manual-review tooling shipped: `python scripts/preview_templates.py` renders the 5×5 grid into `developer/template-previews/` for visual review, and `python cli.py send-test --to verified@inbox` sends a real email through the production `render_email` + SES path with a confirmation prompt. Acceptance criterion 1 (clean dry-run output, no template artifacts) is met. Acceptance criterion 2 (Gmail / Apple Mail render check) is gated on the user actually running `send-test` against a verified inbox.

**Quality wins beyond scope:**

- HTML escaping in `_html_wrap` (`html.escape()` before line-break conversion) prevents broken rendering on names containing `&`, `<`, `>`, or apostrophes — e.g. "Bob's Diner & Co." now renders correctly.
- The Jinja-artifact regression check in `preview_templates.py` is exactly the test that would have caught the original unsubscribe bug; future template tweaks are protected against the same class of mistake.
- `send-test` defaults to `default=False` confirmation and requires `--yes` for non-interactive use — proper safety hygiene around an SES-hitting command.

**Must-fix before merge:**

1. **No `.gitignore`.** `outreach/__pycache__/*.pyc` and `scripts/__pycache__/*.pyc` are committed on this branch. Add a `.gitignore` (Python boilerplate + `.env` + `__pycache__/`), then `git rm --cached -r` the tracked cache directories.
2. **`developer/template-previews/`** is tracked. Since `preview_templates.py` regenerates it on demand, it should be gitignored to avoid 50-file diff churn on every template tweak. Keep the script, drop the artifacts.
3. **`BUSINESS_ADDRESS` in `.env.example` is the placeholder `"ByteStreams LLC, 123 Main St Suite 100, Nashville, TN 37203"`.** Confirm the production `.env` has the real ByteStreams LLC mailing address — the hard guard at render time only catches *unset*, not *set to a fake value*.

**Should-fix (non-blocking):**

- Outscraper references still live in `cli.py:6-7` docstring, `cli.py:31-50` `--source` requirement, and `scripts/import_contacts.py` (`OUTSCRAPER_MAP`, `process_outscraper`, `KNOWN_CHAINS`, Outscraper branch of `passes_quality_filter`). Intentionally deferred to milestone 5 (`Apollo-Only Code Cleanup`, issue #5) — leaving alone is correct, but reviewers may ask why.
- `mailto:` unsubscribe is CAN-SPAM compliant but a fully-qualified `UNSUBSCRIBE_URL` (e.g. a Cloudflare Worker) is more reliable across email clients. Config already supports it via env var — just hasn't been provisioned.
- README does not yet document `send-test` or `preview_templates.py`. Reviewers won't know the manual-review tooling exists.

**Verdict:** Substantively complete. The `.gitignore` omission and the committed cache + preview artifacts are the only real merge blockers — both are ~5-minute fixes.

**Notes:**

- `_JINJA_ARTIFACT_RE = re.compile(r"\{\{[^}]+\}\}")` in `preview_templates.py` only matches complete `{{ ... }}` pairs; a stray bare `{{` or `}}` would slip through. Fine for the current bug class but worth noting.
- `clean_company_name()` is idempotent — running it at both import and render time is intentional defensive engineering for legacy rows imported before the cleanup landed. It is *not* a redundant call to remove.
- `cli.py send-test` sends both text and HTML bodies through the real SES path so what lands in the inbox matches production output exactly. Useful for the verified-inbox acceptance check.

---
