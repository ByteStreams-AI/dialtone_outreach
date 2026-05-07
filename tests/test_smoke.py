"""Smoke tests — every package module must import cleanly.

Catches the obvious breakage class (missing import, syntax error,
removed symbol still referenced) before it lands on main. Bona-fide
unit tests can grow alongside this list as needed.
"""
import importlib

import pytest

MODULES = [
    "outreach",
    "outreach.audit",
    "outreach.cohort",
    "outreach.config",
    "outreach.db",
    "outreach.email_client",
    "outreach.metrics",
    "outreach.preflight",
    "outreach.reply_checker",
    "outreach.runner",
    "outreach.sequence",
    "outreach.sources",
    "outreach.templates",
    "scripts.import_contacts",
    "scripts.preview_templates",
    "web.app",
    "lambda_handler",
    "cli",
]


@pytest.mark.parametrize("module_name", MODULES)
def test_module_imports(module_name: str) -> None:
    importlib.import_module(module_name)
