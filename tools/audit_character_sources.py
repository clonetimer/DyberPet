#!/usr/bin/env python3
"""Offline source catalog lint / freshness audit, with no crawling or login bypass.

Catalog URLs should be verified by a human before rights are interpreted.
Run on CI and periodically; stale records are reported, not silently approved.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from pathlib import Path
from urllib.parse import urlparse

CATALOG = Path(__file__).with_name("character_sources.json")


def check_catalog(catalog=None, *, today=None, max_age_days=90):
    data = catalog if catalog is not None else json.loads(CATALOG.read_text("utf-8"))
    now = today or dt.date.today()
    errors, warnings = [], []
    seen = set()
    for item in data.get("channels", []):
        key = item.get("id")
        if not isinstance(key, str) or not re.fullmatch(r"[a-z0-9_]+", key):
            errors.append("Invalid channel ID")
        if key in seen:
            errors.append("Duplicate channel ID: " + str(key))
        seen.add(key)
        url = urlparse(item.get("url", ""))
        if url.scheme != "https" or not url.netloc:
            errors.append("Channel needs official HTTPS URL: " + str(key))
        if item.get("requires_manual_review") is not True:
            errors.append("Channel must require individual rights review: " + str(key))
        if not item.get("formats"):
            errors.append("Channel missing declared formats: " + str(key))
    candidates = set()
    for row in data.get("candidates", []):
        if row.get("id") in candidates:
            errors.append("Duplicate candidate ID")
        candidates.add(row.get("id"))
        if row.get("channel") not in seen:
            errors.append("Candidate has unknown channel: " + str(row.get("id")))
        if row.get("rights_status") not in ("unknown", "permission_requested",
                                           "evidence_collected", "reviewed"):
            errors.append("Invalid candidate rights_status: " + str(row.get("id")))
        if row.get("rights_status") == "reviewed":
            warnings.append("Candidate catalogue is not proof of permitted use: "
                            + str(row.get("id")))
    try:
        checked = dt.date.fromisoformat(data.get("verified_on", ""))
        age = (now - checked).days
        if age > max_age_days:
            warnings.append(f"Discovery links last manually checked {age} days ago")
        if age < 0:
            errors.append("Catalogue verified_on date is in the future")
    except ValueError:
        age = None
        errors.append("Missing valid verified_on date")
    return {"channels": len(seen), "candidates": len(candidates),
            "last_manually_checked": data.get("verified_on"),
            "age_days": age, "warnings": warnings, "errors": errors,
            "no_remote_requests": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-age-days", type=int, default=90)
    parser.add_argument("--strict-freshness", action="store_true")
    args = parser.parse_args()
    audit = check_catalog(max_age_days=args.max_age_days)
    print(json.dumps(audit, ensure_ascii=False, indent=2))
    if audit["errors"] or (args.strict_freshness and audit["warnings"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
