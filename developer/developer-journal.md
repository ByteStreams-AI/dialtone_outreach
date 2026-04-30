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
