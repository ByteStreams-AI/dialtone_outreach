# Runbook

## Overview

This project is a lightweight lead discovery scraper starter for building city-based lists of restaurants, food trucks, and similar local businesses.

The CLI can:
- show project status
- print demo lead data
- scrape a listing page
- export lead data as CSV or JSON

## Environment setup

This project is managed with [uv](https://docs.astral.sh/uv/). No manual venv activation required.

```bash
# Install uv (one-time, if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# From the project root — installs all dependencies and creates .venv automatically
uv sync
```

That's it. uv handles Python version selection (3.12), the virtual environment, and all packages.

## Basic commands

Prefix every command with `uv run` — no activation needed:

```bash
uv run python cli.py status
```

Or activate once for an interactive session:

```bash
source .venv/bin/activate
python cli.py status
```

Print the demo dataset:

```bash
uv run python cli.py demo
```

Scrape a listing page and print results:

```bash
uv run python cli.py scrape https://example.com/restaurant-directory --limit 20
```

Export scraped results to CSV:

```bash
uv run python cli.py scrape https://example.com/restaurant-directory --limit 20 --export csv --output leads.csv
```

Export scraped results to JSON:

```bash
uv run python cli.py scrape https://example.com/restaurant-directory --limit 20 --export json --output leads.json
```

Fetch Houston food establishment leads:

```bash
uv run python cli.py scrape-houston --limit 50
uv run python cli.py scrape-houston --limit 50 --export csv --output houston_leads.csv
```

Run tests:

```bash
uv run pytest
```

## Adding or updating dependencies

```bash
uv add <package>          # add a runtime dependency
uv add --dev <package>    # add a dev-only dependency
uv remove <package>       # remove a dependency
uv sync                   # sync environment to lockfile after manual edits
```

Never use `pip install` directly — always go through `uv add` so `uv.lock` stays in sync.

## Suggested workflow for city-based lead lists

1. Pick a city or a small set of cities.
2. Find a public directory page that lists restaurants, food trucks, or local businesses.
3. Run the scraper against that page.
4. Export the results to CSV for review.
5. Use the exported fields to do quick call prep research.

## Recommended export fields

The CSV and JSON exports include:
- name
- city
- source
- url
- phone
- address
- notes
- has_website
- has_app
- offers_pickup
- offers_delivery
- delivery_platforms
- uses_doordash_marketing
- uses_chownow

## Notes

This starter is intentionally simple and is best used for:
- testing a source quickly
- validating whether a public listing page is worth scraping
- creating a first-pass lead list for manual research

For more advanced scraping, add a site-specific adapter in the scraper package once you have identified a reliable source.
