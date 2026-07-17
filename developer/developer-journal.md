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

