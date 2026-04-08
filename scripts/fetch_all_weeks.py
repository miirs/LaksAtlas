"""
=============================================================================
LAKSATLAS — Bulk Weekly Data Fetcher
=============================================================================
Fetches all weeks for a given year (default: current year) from the
Barentswatch API. Skips weeks that already have local data files.

Run: python scripts/fetch_all_weeks.py
     python scripts/fetch_all_weeks.py --year 2025
     python scripts/fetch_all_weeks.py --year 2026 --start-week 1 --end-week 13
=============================================================================
"""

import requests
import json
import argparse
import time
from datetime import datetime
from pathlib import Path

# =============================================================================
# CONFIGURATION
# =============================================================================

def load_env():
    env_path = Path(__file__).parent.parent / ".env"
    env = {}
    with open(env_path, "r") as f:
        for line in f:
            if "=" in line:
                key, value = line.strip().split("=", 1)
                env[key] = value
    return env

env = load_env()
CLIENT_ID     = env["CLIENT_ID"]
CLIENT_SECRET = env["CLIENT_SECRET"]

TOKEN_URL = "https://id.barentswatch.no/connect/token"
API_BASE  = "https://www.barentswatch.no/bwapi"
DATA_DIR  = Path(__file__).parent.parent / "data"

# =============================================================================
# AUTH
# =============================================================================

def get_token():
    response = requests.post(TOKEN_URL, data={
        "grant_type":    "client_credentials",
        "client_id":     CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope":         "api"
    })
    response.raise_for_status()
    return response.json()["access_token"]

def refresh_token_if_needed(token, token_time):
    """Re-authenticate if token is older than 50 minutes"""
    if (datetime.now() - token_time).seconds > 3000:
        print("  ↻ Refreshing token...")
        return get_token(), datetime.now()
    return token, token_time

# =============================================================================
# FETCH
# =============================================================================

def fetch_localities(token, year, week):
    r = requests.post(
        f"{API_BASE}/v2/geodata/fishhealth/locality/{year}/{week}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={}
    )
    r.raise_for_status()
    return r.json()

def fetch_summary(token, year, week):
    r = requests.post(
        f"{API_BASE}/v2/geodata/fishhealth/{year}/{week}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={}
    )
    r.raise_for_status()
    return r.json()

# =============================================================================
# SAVE
# =============================================================================

def save_json(data, filepath):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def update_manifest(entries):
    """Write/merge entries into available_weeks.json, sorted newest first"""
    manifest_path = DATA_DIR / "available_weeks.json"

    if manifest_path.exists():
        with open(manifest_path) as f:
            manifest = json.load(f)
    else:
        manifest = {"weeks": []}

    # Merge: remove duplicates then add all new entries
    existing = {(w["year"], w["week"]): w for w in manifest["weeks"]}
    for e in entries:
        existing[(e["year"], e["week"])] = e

    manifest["weeks"] = sorted(existing.values(), key=lambda w: (w["year"], w["week"]), reverse=True)
    manifest["latest"] = {"year": manifest["weeks"][0]["year"], "week": manifest["weeks"][0]["week"]}

    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

# =============================================================================
# DETERMINE WEEK RANGE
# =============================================================================

def get_latest_completed_week(year):
    """Return the last fully-reported ISO week for a given year"""
    today = datetime.now()
    # Walk back until we're in the right year or find the last week
    from datetime import timedelta
    check = today - timedelta(days=7)
    while check.isocalendar()[0] > year:
        check -= timedelta(days=7)
    if check.isocalendar()[0] < year:
        # Year is complete — find its last week
        dec28 = datetime(year, 12, 28)
        return dec28.isocalendar()[1]
    return check.isocalendar()[1]

# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Bulk-fetch weekly Barentswatch data")
    parser.add_argument("--year",       type=int, default=datetime.now().year)
    parser.add_argument("--start-week", type=int, default=1)
    parser.add_argument("--end-week",   type=int, default=None)
    args = parser.parse_args()

    year = args.year
    start_week = args.start_week
    end_week   = args.end_week or get_latest_completed_week(year)

    print("=" * 60)
    print(f"LAKSATLAS — Bulk Fetch: {year} weeks {start_week}–{end_week}")
    print("=" * 60)

    DATA_DIR.mkdir(exist_ok=True)

    # Authenticate
    token = get_token()
    token_time = datetime.now()
    print("OK Authenticated\n")

    new_entries = []
    skipped = 0
    fetched = 0
    failed  = []

    for week in range(start_week, end_week + 1):
        w_str = str(week).zfill(2)
        loc_path = DATA_DIR / f"localities_{year}_{w_str}.json"

        if loc_path.exists():
            print(f"  week {w_str}  [skip — already downloaded]")
            skipped += 1
            continue

        token, token_time = refresh_token_if_needed(token, token_time)

        try:
            localities = fetch_localities(token, year, week)
            summary    = fetch_summary(token, year, week)

            metadata = {
                "fetched_at":       datetime.now().isoformat(),
                "year":             year,
                "week":             week,
                "total_localities": len(localities)
            }

            save_json({"metadata": metadata, "localities": localities}, loc_path)
            save_json({"metadata": metadata, "summary": summary},       DATA_DIR / f"summary_{year}_{w_str}.json")

            new_entries.append({
                "year":             year,
                "week":             week,
                "fetched_at":       metadata["fetched_at"],
                "total_localities": len(localities)
            })

            fetched += 1
            print(f"  week {w_str}  OK  {len(localities)} localities")

            # Small delay to avoid hammering the API
            time.sleep(0.4)

        except Exception as e:
            failed.append(week)
            print(f"  week {w_str}  FAIL  {e}")

    # Update manifest with all new entries
    if new_entries:
        update_manifest(new_entries)

    # Also update localities.json / summary.json to point at the latest week fetched
    latest_w = str(end_week).zfill(2)
    latest_loc = DATA_DIR / f"localities_{year}_{latest_w}.json"
    if latest_loc.exists():
        import shutil
        shutil.copy(latest_loc,                              DATA_DIR / "localities.json")
        shutil.copy(DATA_DIR / f"summary_{year}_{latest_w}.json", DATA_DIR / "summary.json")

    print(f"\n{'=' * 60}")
    print(f"Done.  fetched: {fetched}  skipped: {skipped}  failed: {len(failed)}")
    if failed:
        print(f"Failed weeks: {failed}")
    print("=" * 60)

if __name__ == "__main__":
    main()
