"""
=============================================================================
LAKSATLAS — Locality Geo Fetcher
=============================================================================
Fetches farm coordinates for week 26 (mid-year peak) of each year 2020–2024
from the Barentswatch Fishhealth API.

For each year it saves data/localities_geo_YEAR.json containing:
  - "points":  [[lat,lng], ...]  — all farm coordinates (for heatmap)
  - "regions": { "Nordland": {"count":N, "mean_nn_km":X}, ... }
               mean_nn_km = mean nearest-neighbour distance in km,
               i.e. the average distance from each farm to its closest
               neighbouring farm within the same region.
               Lower value → farms are genuinely clustered together.

Run: python scripts/fetch_localities_geo.py
=============================================================================
"""

import requests
import json
import math
from pathlib import Path

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

YEARS = [2020, 2021, 2022, 2023, 2024, 2025]
WEEK  = 26   # mid-year snapshot

TOKEN_URL = "https://id.barentswatch.no/connect/token"
API_BASE  = "https://www.barentswatch.no/bwapi"

# ---------------------------------------------------------------------------
# REGION BOUNDING BOXES
# 2020-2022: Troms og Finnmark was one county
# 2023-2024: split into Troms and Finnmark
# Latitude bands are approximate — good enough for mean NN distance calc
# ---------------------------------------------------------------------------

def assign_region(lat, lng, year):
    if lat >= 70.3:
        return "Finnmark" if year >= 2023 else "Troms og Finnmark"
    if lat >= 68.2:
        return "Troms" if year >= 2023 else "Troms og Finnmark"
    if lat >= 65.0:
        return "Nordland"
    if lat >= 63.3:
        return "Trøndelag"
    if lat >= 62.0:
        return "Møre og Romsdal"
    if lat >= 59.5:
        return "Vestland"
    return "Rogaland"

# ---------------------------------------------------------------------------
# HAVERSINE — distance in km between two lat/lng points
# ---------------------------------------------------------------------------

def haversine(lat1, lng1, lat2, lng2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1))
         * math.cos(math.radians(lat2))
         * math.sin(dlng / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))

# ---------------------------------------------------------------------------
# MEAN NEAREST-NEIGHBOUR DISTANCE
# For each farm find its closest farm in the same region, then average.
# O(n²) but n ≤ ~300 per region, runs in <1 s per region.
# ---------------------------------------------------------------------------

def mean_nn_km(points):
    """Returns average nearest-neighbour distance (km), or None if < 2 points."""
    if len(points) < 2:
        return None
    nn_dists = []
    for i, p1 in enumerate(points):
        best = float("inf")
        for j, p2 in enumerate(points):
            if i == j:
                continue
            d = haversine(p1[0], p1[1], p2[0], p2[1])
            if d < best:
                best = d
        nn_dists.append(best)
    return round(sum(nn_dists) / len(nn_dists), 2)

# ---------------------------------------------------------------------------
# CREDENTIALS
# ---------------------------------------------------------------------------

def load_env():
    env_path = Path(__file__).parent.parent / ".env"
    env = {}
    with open(env_path) as f:
        for line in f:
            if "=" in line:
                k, v = line.strip().split("=", 1)
                env[k] = v
    return env

def get_token(env):
    print("Authenticating with Barentswatch...")
    r = requests.post(TOKEN_URL, data={
        "grant_type":    "client_credentials",
        "client_id":     env["CLIENT_ID"],
        "client_secret": env["CLIENT_SECRET"],
        "scope":         "api"
    })
    r.raise_for_status()
    print("  ✓ Token obtained\n")
    return r.json()["access_token"]

# ---------------------------------------------------------------------------
# FETCH ONE YEAR/WEEK
# ---------------------------------------------------------------------------

def fetch_year(token, year, week):
    print(f"  Fetching {year} week {week}...", end=" ", flush=True)
    r = requests.post(
        f"{API_BASE}/v2/geodata/fishhealth/locality/{year}/{week}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={}
    )
    r.raise_for_status()
    data = r.json()

    all_points = []
    region_points = {}

    for loc in data:
        geo = loc.get("geometry") or {}
        coords = geo.get("coordinates")
        if not coords or len(coords) < 2:
            continue
        lng, lat = coords[0], coords[1]
        if not lat or not lng:
            continue

        pt = [round(lat, 5), round(lng, 5)]
        all_points.append(pt)

        region = assign_region(lat, lng, year)
        region_points.setdefault(region, []).append(pt)

    print(f"{len(all_points)} localities with coordinates")
    return all_points, region_points

# ---------------------------------------------------------------------------
# BUILD REGION STATS
# ---------------------------------------------------------------------------

def build_region_stats(region_points):
    stats = {}
    for region, pts in region_points.items():
        nn = mean_nn_km(pts)
        stats[region] = {
            "count": len(pts),
            "mean_nn_km": nn
        }
        print(f"    {region}: {len(pts)} farms, avg NN = {nn} km")
    return stats

# ---------------------------------------------------------------------------
# SAVE
# ---------------------------------------------------------------------------

def save(year, week, points, region_stats):
    data_dir = Path(__file__).parent.parent / "data"
    data_dir.mkdir(exist_ok=True)
    path = data_dir / f"localities_geo_{year}.json"
    payload = {
        "year": year,
        "week": week,
        "count": len(points),
        "points": points,
        "regions": region_stats
    }
    with open(path, "w") as f:
        json.dump(payload, f, separators=(",", ":"))
    kb = path.stat().st_size / 1024
    print(f"  ✓ Saved {path.name} ({kb:.0f} KB)")

# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("LAKSATLAS — Locality Geo Fetch")
    print(f"Fetching week {WEEK} for years: {YEARS}")
    print("=" * 60 + "\n")

    env   = load_env()
    token = get_token(env)

    for year in YEARS:
        print(f"Year {year}:")
        try:
            points, region_points = fetch_year(token, year, WEEK)
            print(f"  Region breakdown:")
            stats = build_region_stats(region_points)
            save(year, WEEK, points, stats)
        except Exception as e:
            print(f"  ✗ Failed: {e}")
        print()

    print("Done.")
    print("Nearest-neighbour distances are in data/localities_geo_YEAR.json")
    print("These feed the Farm Clustering bubble chart in each year page.")

if __name__ == "__main__":
    main()
