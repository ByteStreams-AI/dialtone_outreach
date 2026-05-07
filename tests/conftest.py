"""Populate dummy env vars before any ``outreach`` module is imported.

``outreach.config`` reads required env vars (``SUPABASE_URL``, ``AWS_*``,
``FROM_EMAIL``) at import time and raises ``KeyError`` if any are
missing. The smoke test suite imports every module to catch syntax
errors and missing references — it does not need real credentials.
"""
import os

_DEFAULTS = {
    "SUPABASE_URL": "https://example.supabase.co",
    "SUPABASE_SERVICE_KEY": "dummy-service-key",
    "AWS_ACCESS_KEY_ID": "AKIA-DUMMY",
    "AWS_SECRET_ACCESS_KEY": "dummy-secret",
    "AWS_REGION": "us-east-1",
    "FROM_EMAIL": "test@example.com",
    "BUSINESS_ADDRESS": "123 Test St, Test City, TS 00000",
}

for key, value in _DEFAULTS.items():
    os.environ.setdefault(key, value)
