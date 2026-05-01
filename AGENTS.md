# AGENTS.md

Operating manual for AI coding agents (Warp / Oz, Claude Code, etc.) working
inside this repo. Humans should read [README.md](README.md) first; this file
captures the conventions an agent needs to be productive without breaking
anything live.

## Project at a glance

DialTone Outreach is a cold-email sequencer for restaurant owners.

- **Stack:** AWS SES + Supabase (Postgres) + Click/Rich CLI, with a planned
  local FastAPI + Jinja2 + HTMX UI for non-technical reviewers.
- **Source of truth for milestones:** [docs/project-status.md](docs/project-status.md).
  Every milestone there has a matching GitHub issue on
  `ByteStreams-AI/dialtone_outreach`.
- **Active branch:** feature work happens on `chore/*` or `feat/*` branches
  that target `main` via PR. Never push directly to `main`.

## Repo layout

```
cli.py                       Click entry point for every command
schema.sql                   Supabase DDL (run once)
.env.example                 Copy to .env and fill in credentials
docs/
  project-status.md          Milestone tracker (keep current after each PR)
  apollo-contacts-export.csv Sample Apollo export used by preview tooling
outreach/
  config.py                  Settings loaded from .env (Status enum lives here)
  db.py                      Supabase client + query helpers
  email_client.py            AWS SES wrapper
  sequence.py                Day-N timing logic
  templates.py               5 Jinja2 templates + CAN-SPAM helpers
  runner.py                  Orchestration loop + Rich dashboard
scripts/
  import_contacts.py         Apollo CSV importer
  preview_templates.py       Render all 5 templates against real Apollo rows
developer/
  developer-journal.md       Running engineering log
  cohorts/                   Locked-cohort JSON snapshots (gitignored)
  template-previews/         Generated HTML / text previews (gitignored)
```

## Environment

- Python 3.12+ (`pyproject.toml` pins `requires-python = ">=3.12.12"`).
- Dependencies are pinned in `requirements.txt` and locked in `uv.lock`.
- Preferred workflow uses [uv](https://docs.astral.sh/uv/):

  ```bash
  uv venv
  source .venv/bin/activate
  uv pip install -r requirements.txt
  ```

- `.env` is required for anything that touches `outreach.config`. Use
  `.env.example` as a template; never commit a real `.env`.
- `BUSINESS_ADDRESS` must be set before any template rendering — `render_email()`
  raises if it isn't (CAN-SPAM guardrail).

## CLI cheatsheet

```bash
python cli.py import --source apollo --file apollo_export.csv [--dry-run]
python cli.py run [--dry-run] [--limit N]
python cli.py status
python cli.py stats
python cli.py contact --email owner@example.com
python cli.py contact --domain example.com
python cli.py send-test --to verified@inbox.example [--seq 1] [--yes]
python cli.py preflight
python cli.py cohort lock   --name batch-1 --limit 5
python cli.py cohort show   [--name batch-1]
python cli.py cohort unlock --name batch-1
python cli.py run --dry-run --cohort batch-1
python cli.py metrics --since 7d
python cli.py metrics --cohort batch-1
python scripts/preview_templates.py [--csv PATH] [--out DIR] [--count N]
```

`run` without `--dry-run` sends real email. Always start with `--dry-run`
when verifying changes that touch sequencing, templates, or filtering. The
M2 live cohort flow (`preflight` → `cohort lock` → `run --cohort`
→ `metrics`) is documented in `docs/runbook-first-cohort.md`; cohorts under
`developer/cohorts/` are gitignored because they contain recipient PII.

## Coding conventions

- **Docstrings:** Google style on every public class and function. Match the
  existing voice in `outreach/templates.py` and `scripts/preview_templates.py`.
- **Type hints:** use them on public function signatures.
- **Imports:** stdlib → third-party → local, separated by blank lines.
- **Status values:** use the `outreach.config.Status` constants instead of
  bare strings. Same for `TERMINAL_STATUSES` and `SEQUENCE_STATUS_MAP`.
- **Templates:** edit Jinja strings directly in `outreach/templates.py`. Do
  not add f-string-style template substitution — it caused the
  `{{ unsubscribe_url }}` brace-leak that motivated milestone 1. Anything
  rendered into the body must flow through the Jinja context.
- **CAN-SPAM:** every commercial email must include `BUSINESS_ADDRESS`,
  `COMPANY_LEGAL_NAME`, sender identity, and a working unsubscribe link. The
  helpers in `outreach/templates.py` already do this — keep them as the only
  HTML/text wrappers.
- **Contact column allowlist:** `scripts/import_contacts.py::CONTACT_COLUMNS`
  mirrors the columns on the `contacts` table in `schema.sql`. The import
  loop filters every CSV row through it so Apollo's extra columns
  (`# Employees`, `Industry`, `Annual Revenue`, etc.) are dropped before the
  upsert. **If you add a column to `schema.sql`, add it to `CONTACT_COLUMNS`
  too** — otherwise it will be silently dropped during import. Conversely,
  if you remove a column from the schema, remove it here so the upsert
  doesn't try to write a non-existent field.

## Verification before handing work back

1. Run `python cli.py run --dry-run` against a populated database when
   touching `outreach/runner.py`, `outreach/sequence.py`, or
   `outreach/db.py`.
2. Run `python scripts/preview_templates.py` whenever you change
   `outreach/templates.py` or `scripts/import_contacts.py::process_apollo`.
   The script exits non-zero if any rendered file still contains a
   `{{ ... }}` artifact, so it doubles as a smoke test.
3. For send-path changes, finish with
   `python cli.py send-test --to verified@inbox.example` and visually
   confirm Gmail and Apple Mail rendering.
4. There is no formal lint/test harness yet (see milestone 6). At minimum,
   `python -c "import outreach, scripts"` should succeed.

## Branch and commit policy

- **Never** make changes directly on `main`. Branch from `main` using
  `feat/<topic>`, `fix/<topic>`, or `chore/<topic>`.
- **Never** stage or commit on the user's behalf unless they explicitly ask
  for it. Leave files modified in the working tree and let the user review.
- When the user does ask for a commit, follow Conventional Commits:

  ```
  <type>(<scope>): <subject>

  <body — optional, wrap at ~72 chars>

  Co-Authored-By: Oz <oz-agent@warp.dev>
  ```

  Common types: `feat`, `fix`, `chore`, `docs`, `refactor`, `test`. Common
  scopes used so far: `app`, `templates`, `cli`, `docs`.
- Refresh `docs/project-status.md` whenever a milestone step lands so the
  tracker stays the source of truth.

## Things to avoid

- Sending real email from agent runs. Use `--dry-run` and the verified
  inbox in `send-test`.
- Restoring Outscraper or merge code paths — milestone 5 is to delete them.
- Adding new env vars without documenting them in both `.env.example` and
  the README's "Environment Variables Reference" table.
- Editing `uv.lock` by hand. Regenerate with `uv lock` after touching
  `pyproject.toml` or `requirements.txt`.
