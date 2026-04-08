"""
=============================================================================
LAKSATLAS — Barentswatch Data Fetcher
=============================================================================
This script authenticates with the Barentswatch API and downloads
all salmon farming locality data for a given week.

Run: python scripts/fetch_data.py
Output: data/localities.json, data/summary.json
=============================================================================
"""

import requests
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

# =============================================================================
# SECTION 1: CONFIGURATION
# Load API credentials from .env file in project root
# =============================================================================

def load_credentials():
    """
    Load CLIENT_ID and CLIENT_SECRET.
    Priority: environment variables (GitHub Actions / CI) → .env file (local dev).
    """
    client_id = os.environ.get("CLIENT_ID")
    client_secret = os.environ.get("CLIENT_SECRET")
    if client_id and client_secret:
        return client_id, client_secret

    # Fallback: read .env file for local development
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        raise RuntimeError(
            "No credentials found. Set CLIENT_ID and CLIENT_SECRET environment "
            "variables, or create a .env file in the project root."
        )
    env = {}
    with open(env_path, "r") as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                key, value = line.split("=", 1)
                env[key.strip()] = value.strip()
    return env["CLIENT_ID"], env["CLIENT_SECRET"]

CLIENT_ID, CLIENT_SECRET = load_credentials()

TOKEN_URL = "https://id.barentswatch.no/connect/token"
API_BASE = "https://www.barentswatch.no/bwapi"

# =============================================================================
# SECTION 2: AUTHENTICATION
# Get OAuth2 bearer token using client_credentials flow
# =============================================================================

def get_token():
    """Authenticate with Barentswatch and return access token"""
    print("Authenticating with Barentswatch...")
    response = requests.post(TOKEN_URL, data={
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope": "api"
    })
    response.raise_for_status()
    token = response.json()["access_token"]
    print("  ✓ Authentication successful\n")
    return token

# =============================================================================
# SECTION 3: DETERMINE CURRENT WEEK
# Lice data is reported weekly (deadline: Tuesday of following week)
# So we fetch the most recent completed week
# =============================================================================

def get_latest_week():
    """Return (year, week) for the most recently completed reporting week"""
    today = datetime.now()
    # Go back 7 days to ensure the week is fully reported
    last_week = today - timedelta(days=7)
    year = last_week.isocalendar()[0]
    week = last_week.isocalendar()[1]
    return year, week

# =============================================================================
# SECTION 4: FETCH ALL LOCALITY DATA
# This is the main dataset — every active salmon farm in Norway
# with coordinates, lice counts, disease status, treatments
# =============================================================================

def fetch_localities(token, year, week):
    """Fetch all locality data for a given week"""
    print(f"Fetching all localities for {year} week {week}...")
    response = requests.post(
        f"{API_BASE}/v2/geodata/fishhealth/locality/{year}/{week}",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        },
        json={}
    )
    response.raise_for_status()
    data = response.json()
    print(f"  ✓ Got {len(data)} localities\n")
    return data

# =============================================================================
# SECTION 5: FETCH NATIONAL SUMMARY
# Overview stats: disease outbreaks, escape numbers, lice threshold stats
# =============================================================================

def fetch_summary(token, year, week):
    """Fetch national summary statistics for a given week"""
    print(f"Fetching national summary for {year} week {week}...")
    response = requests.post(
        f"{API_BASE}/v2/geodata/fishhealth/{year}/{week}",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        },
        json={}
    )
    response.raise_for_status()
    data = response.json()
    print(f"  ✓ Got summary data\n")
    return data

# =============================================================================
# SECTION 6: SAVE DATA TO JSON FILES
# Save to data/ folder for the website to read
# =============================================================================

def save_json(data, filename):
    """Save data as formatted JSON file in the data/ directory"""
    data_dir = Path(__file__).parent.parent / "data"
    data_dir.mkdir(exist_ok=True)
    filepath = data_dir / filename
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    size_mb = filepath.stat().st_size / (1024 * 1024)
    print(f"  ✓ Saved {filepath} ({size_mb:.1f} MB)")


def update_manifest(year, week, fetched_at):
    """Update data/available_weeks.json with the newly fetched week"""
    data_dir = Path(__file__).parent.parent / "data"
    manifest_path = data_dir / "available_weeks.json"

    # Load existing manifest if present
    if manifest_path.exists():
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    else:
        manifest = {"weeks": []}

    # Remove duplicate entry for this week if it exists
    manifest["weeks"] = [
        w for w in manifest["weeks"]
        if not (w["year"] == year and w["week"] == week)
    ]

    # Prepend this week (newest first)
    manifest["weeks"].insert(0, {
        "year": year,
        "week": week,
        "fetched_at": fetched_at,
        "total_localities": None  # filled below
    })

    # Sort newest first
    manifest["weeks"].sort(key=lambda w: (w["year"], w["week"]), reverse=True)
    manifest["latest"] = {"year": manifest["weeks"][0]["year"], "week": manifest["weeks"][0]["week"]}

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"  ✓ Updated available_weeks.json ({len(manifest['weeks'])} weeks)")

# =============================================================================
# SECTION 7: MAIN — Run everything
# =============================================================================

def main():
    print("=" * 60)
    print("LAKSATLAS — Data Fetch")
    print("=" * 60 + "\n")

    # Authenticate
    token = get_token()

    # Determine which week to fetch
    year, week = get_latest_week()
    print(f"Target: {year} week {week}\n")

    # Fetch data
    localities = fetch_localities(token, year, week)
    summary = fetch_summary(token, year, week)

    # Add metadata
    metadata = {
        "fetched_at": datetime.now().isoformat(),
        "year": year,
        "week": week,
        "total_localities": len(localities)
    }

    # Save everything
    print("\nSaving data...")
    week_str = f"{year}_{str(week).zfill(2)}"
    loc_payload  = {"metadata": metadata, "localities": localities}
    sum_payload  = {"metadata": metadata, "summary": summary}

    # Always overwrite "latest" files (used as fallback)
    save_json(loc_payload, "localities.json")
    save_json(sum_payload, "summary.json")

    # Also save week-specific files for historical browsing
    save_json(loc_payload, f"localities_{week_str}.json")
    save_json(sum_payload, f"summary_{week_str}.json")

    # Update the manifest of available weeks
    update_manifest(year, week, metadata["fetched_at"])

    # Quick stats
    print(f"\n{'=' * 60}")
    print(f"Done! {len(localities)} localities saved.")

    # Count some basic stats from the data
    reported = sum(1 for loc in localities
                   if loc.get("liceReport", {}).get("hasReported", False))
    above_limit = sum(1 for loc in localities
                      if (loc.get("liceReport", {})
                          .get("adultFemaleLice", {})
                          .get("average") or 0) > 0.5)
    with_disease = sum(1 for loc in localities
                       if loc.get("diseases"))

    print(f"  Reported lice this week: {reported}")
    print(f"  Above 0.5 lice limit:   {above_limit}")
    print(f"  With active disease:     {with_disease}")
    print("=" * 60)

if __name__ == "__main__":
    main()