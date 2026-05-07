"""lambda_handler.py — AWS Lambda entrypoint for scheduled outreach jobs.

Dispatches to one of the existing CLI surfaces based on the EventBridge
event payload's ``task`` field:

    {"task": "run"}              → outreach.runner.run(dry_run=False)
    {"task": "run", "cohort": "batch-1"}
    {"task": "check-replies"}    → outreach.reply_checker.check_replies()
    {"task": "preflight"}        → outreach.preflight.run_preflight()

EventBridge schedules pass the input via ``event``; ``context`` carries
the AWS request id which we log for cross-referencing with CloudWatch.

Logging: stdout/stderr is captured by the Lambda runtime into
CloudWatch Logs automatically. Each invocation logs a structured start
and end line so log scans can pivot on ``task`` and ``request_id``.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("dialtone.lambda")


def handler(event: dict[str, Any] | None, context: Any) -> dict[str, Any]:
    """Lambda entrypoint. Returns a JSON-serialisable summary dict."""
    event = event or {}
    task = event.get("task", "run")
    request_id = getattr(context, "aws_request_id", "local")

    log.info("start task=%s request_id=%s event=%s", task, request_id, json.dumps(event))

    try:
        result = _dispatch(task, event)
    except Exception:
        log.exception("task=%s request_id=%s failed", task, request_id)
        raise

    log.info("done task=%s request_id=%s result=%s", task, request_id, json.dumps(result))
    return {"task": task, "request_id": request_id, **result}


def _dispatch(task: str, event: dict[str, Any]) -> dict[str, Any]:
    if task == "run":
        from outreach.runner import run

        run(
            dry_run=bool(event.get("dry_run", False)),
            limit=event.get("limit"),
            cohort=event.get("cohort"),
        )
        return {"status": "ok"}

    if task == "check-replies":
        from outreach.reply_checker import check_replies

        result = check_replies(dry_run=bool(event.get("dry_run", False)))
        return {
            "scanned": result.scanned,
            "matched": result.matched,
            "skipped": result.skipped,
            "errors": result.errors,
        }

    if task == "preflight":
        from outreach.preflight import run_preflight

        return {"exit_code": run_preflight()}

    raise ValueError(
        f"Unknown task {task!r}. Expected one of: run, check-replies, preflight."
    )
