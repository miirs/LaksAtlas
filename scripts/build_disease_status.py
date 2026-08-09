"""
=============================================================================
LAKSATLAS — Disease Status Registry Builder
=============================================================================
Barentswatch's `diseaseOutbreaks` field (inside the weekly summary payload)
is NOT a persistent status list — it only reports outbreaks that were newly
SUSPECTED or newly DIAGNOSED during that specific week. A disease that has
been active on a locality for months will only appear in this feed on the
one week its status changed.

This script scans every archived weekly summary file in data/ and builds a
persistent per-locality, per-disease status history, so the map can show
something like "PD — suspected since week 5, diagnosed week 12" instead of
just the bare disease code.

Run: python scripts/build_disease_status.py
Output: data/disease_status.json

Also called automatically from fetch_data.py after each weekly fetch, so the
registry keeps accumulating going forward.
=============================================================================
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
WEEK_FILE_RE = re.compile(r"^summary_(\d{4})_(\d{2})\.json$")


def week_key(year, week):
    return (year, week)


def load_weekly_summary_files():
    """Find every dated summary_<year>_<week>.json file, sorted chronologically."""
    files = []
    for path in DATA_DIR.glob("summary_*.json"):
        m = WEEK_FILE_RE.match(path.name)
        if not m:
            continue
        year, week = int(m.group(1)), int(m.group(2))
        files.append((year, week, path))
    files.sort(key=lambda x: (x[0], x[1]))
    return files


def build_registry():
    """
    Returns:
      {
        "<locality_no>": {
          "<disease_code>": {
            "latest_status": "SUSPECTED" | "DIAGNOSED",
            "latest_year": int, "latest_week": int,
            "first_suspected_year": int|None, "first_suspected_week": int|None,
            "diagnosed_year": int|None, "diagnosed_week": int|None,
            "subtype": str|None,
            "locality_name": str
          }, ...
        }, ...
      }
    """
    registry = {}
    files = load_weekly_summary_files()

    for year, week, path in files:
        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        outbreaks = (payload.get("summary") or {}).get("diseaseOutbreaks") or []
        for ob in outbreaks:
            loc = ob.get("locality") or {}
            dis = ob.get("disease") or {}
            no = loc.get("no")
            code = dis.get("name")
            status = dis.get("status")
            subtype = dis.get("subType")
            if no is None or not code or not status:
                continue

            no_key = str(no)
            entry = registry.setdefault(no_key, {}).setdefault(code, {
                "latest_status": None, "latest_year": None, "latest_week": None,
                "first_suspected_year": None, "first_suspected_week": None,
                "diagnosed_year": None, "diagnosed_week": None,
                "subtype": None, "locality_name": loc.get("name"),
            })

            # Files are processed in chronological order, so the last write wins for "latest"
            entry["latest_status"] = status
            entry["latest_year"] = year
            entry["latest_week"] = week
            entry["locality_name"] = loc.get("name") or entry["locality_name"]
            if subtype:
                entry["subtype"] = subtype

            if status == "SUSPECTED" and entry["first_suspected_year"] is None:
                entry["first_suspected_year"] = year
                entry["first_suspected_week"] = week
            if status == "DIAGNOSED" and entry["diagnosed_year"] is None:
                entry["diagnosed_year"] = year
                entry["diagnosed_week"] = week

    return registry


def build_and_save():
    registry = build_registry()
    files = load_weekly_summary_files()
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_note": "Accumulated from Barentswatch's weekly diseaseOutbreaks feed, "
                        "which only reports newly SUSPECTED/DIAGNOSED cases per week. "
                        "Localities/diseases never seen in that feed have no entry here.",
        "weeks_scanned": len(files),
        "localities": registry,
    }
    out_path = DATA_DIR / "disease_status.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    size_kb = out_path.stat().st_size / 1024
    print(f"  ✓ Saved {out_path} ({size_kb:.1f} KB, {len(files)} weeks scanned, "
          f"{sum(len(v) for v in registry.values())} locality-disease entries)")
    return output


if __name__ == "__main__":
    print("=" * 60)
    print("LAKSATLAS — Building disease status registry")
    print("=" * 60 + "\n")
    build_and_save()
