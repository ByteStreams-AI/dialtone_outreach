"""Populate dummy env vars before any ``outreach`` module is imported.

``outreach.config`` reads ``SUPABASE_URL``, ``SUPABASE_SERVICE_KEY``,
``FROM_EMAIL``, and ``BUSINESS_ADDRESS`` at import time and raises
``KeyError`` if any are missing. The smoke test suite imports every
module to catch syntax errors and missing references — it does not
need real credentials. AWS access keys are intentionally absent: the
app no longer reads them at import (boto3 resolves credentials at
call time), so the smoke test should not require them either.
"""
import os

_DEFAULTS = {
    "SUPABASE_URL": "https://example.supabase.co",
    "SUPABASE_SERVICE_KEY": "dummy-service-key",
    "AWS_REGION": "us-east-1",
    "FROM_EMAIL": "test@example.com",
    "BUSINESS_ADDRESS": "123 Test St, Test City, TS 00000",
}

for key, value in _DEFAULTS.items():
    os.environ.setdefault(key, value)
