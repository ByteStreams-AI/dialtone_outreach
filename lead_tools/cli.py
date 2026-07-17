"""Small command helpers for the starter lead-discovery workflow."""

from . import Lead, collect_leads


def render_leads(leads: list[Lead]) -> str:
    """Return a short text report of the provided leads."""

    if not leads:
        return "No leads collected yet."

    lines = [f"{lead.name} | {lead.city} | {lead.source}" for lead in leads]
    return "\n".join(lines)


def seed_demo_leads() -> list[Lead]:
    """Provide a tiny demo dataset for local development."""

    return collect_leads(
        [
            Lead("Example Restaurant", "Nashville", "demo", "https://example.com"),
            Lead("River Street Cafe", "Memphis", "demo", "https://example.com/river"),
        ]
    )
