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

def load_env():
    """Read .env file and return credentials as dict"""
    env_path = Path(__file__).parent.parent / ".env"
    env = {}
    with open(env_path, "r") as f:
        for line in f:
            if "=" in line:
                key, value = line.strip().split("=", 1)
                env[key] = value
    return env

env = load_env()
CLIENT_ID = env["CLIENT_ID"]
CLIENT_SECRET = env["CLIENT_SECRET"]

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
    save_json({"metadata": metadata, "localities": localities}, "localities.json")
    save_json({"metadata": metadata, "summary": summary}, "summary.json")

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