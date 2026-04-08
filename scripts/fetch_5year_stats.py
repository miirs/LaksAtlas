"""
=============================================================================
LAKSATLAS — 5-Year Weekly Stats Fetcher
=============================================================================
Fetches locality data for each week of each target year and saves only
lightweight aggregate stats (not raw locality data) to:

  data/5year_weekly_stats.json

Each entry is one week:
  { year, week, totalLocalities, reporting, fallow, aboveLimit,
    aboveModerate, avgLice, avgTemp, diseaseCount, municipalities }

This feeds the 5-Year Bubble View on the live map page.

Usage:
  python scripts/fetch_5year_stats.py
  python scripts/fetch_5year_stats.py --years 2022 2023 2024 2025

Skips weeks already present in the output file.
=============================================================================
"""

import requests, json, math, time, argparse
from pathlib import Path
from datetime import datetime

# ---------------------------------------------------------------------------
TOKEN_URL = "https://id.barentswatch.no/connect/token"
API_BASE  = "https://www.barentswatch.no/bwapi"
OUT_FILE  = Path(__file__).parent.parent / "data" / "5year_weekly_stats.json"
ENV_FILE  = Path(__file__).parent.parent / ".env"
DEFAULT_YEARS = [2021, 2022, 2023, 2024, 2025]
WEEKS_PER_YEAR = 52
DELAY = 0.5        # seconds between API calls
TOKEN_TTL = 2900   # seconds before refreshing token (~48 min)
# ---------------------------------------------------------------------------

def load_env():
    env = {}
    with open(ENV_FILE) as f:
        for line in f:
            if "=" in line:
                k, v = line.strip().split("=", 1)
                env[k.strip()] = v.strip()
    return env

def get_token(env):
    r = requests.post(TOKEN_URL, data={
        "grant_type": "client_credentials",
        "client_id":     env["CLIENT_ID"],
        "client_secret": env["CLIENT_SECRET"],
        "scope": "api"
    })
    r.raise_for_status()
    return r.json()["access_token"]

def compute_stats(localities):
    total = len(localities)
    fallow = sum(1 for l in localities if (l.get("liceReport") or {}).get("isFallow"))
    reporting = sum(1 for l in localities if (l.get("liceReport") or {}).get("hasReported") and not (l.get("liceReport") or {}).get("isFallow"))
    active = [l for l in localities if (l.get("liceReport") or {}).get("hasReported") and not (l.get("liceReport") or {}).get("isFallow")]
    lice_vals = [l["liceReport"]["adultFemaleLice"]["average"] for l in active
                 if (l.get("liceReport") or {}).get("adultFemaleLice") and l["liceReport"]["adultFemaleLice"].get("average") is not None]
    temp_vals = [l["liceReport"]["seaTemperature"] for l in localities
                 if (l.get("liceReport") or {}).get("seaTemperature") and l["liceReport"]["seaTemperature"] > 0]
    above_limit   = sum(1 for v in lice_vals if v > 0.5)
    above_moderate = sum(1 for v in lice_vals if 0.2 < v <= 0.5)
    avg_lice = round(sum(lice_vals) / len(lice_vals), 4) if lice_vals else None
    avg_temp = round(sum(temp_vals) / len(temp_vals), 2) if temp_vals else None
    disease_count = sum(1 for l in localities if l.get("diseases"))
    municipalities = len({(l.get("municipality") or {}).get("name") for l in localities if (l.get("municipality") or {}).get("name")})
    return {
        "totalLocalities": total,
        "reporting": reporting,
        "fallow": fallow,
        "aboveLimit": above_limit,
        "aboveModerate": above_moderate,
        "avgLice": avg_lice,
        "avgTemp": avg_temp,
        "diseaseCount": disease_count,
        "municipalities": municipalities,
    }

def fetch_week(token, year, week):
    r = requests.post(
        f"{API_BASE}/v2/geodata/fishhealth/locality/{year}/{week}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={}, timeout=30
    )
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()

def load_existing():
    if OUT_FILE.exists():
        with open(OUT_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"generated_at": None, "weeks": []}

def save(data):
    data["generated_at"] = datetime.utcnow().isoformat()
    # Sort by year then week
    data["weeks"].sort(key=lambda w: (w["year"], w["week"]))
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, separators=(",", ":"))
    kb = OUT_FILE.stat().st_size / 1024
    print(f"  Saved {OUT_FILE.name} ({kb:.0f} KB, {len(data['weeks'])} week entries)")

def main():
    parser = argparse.ArgumentParser(description="Fetch 5-year weekly stats for LaksAtlas bubble view")
    parser.add_argument("--years", nargs="+", type=int, default=DEFAULT_YEARS, help="Years to fetch")
    args = parser.parse_args()

    print("=" * 60)
    print("LAKSATLAS - 5-Year Weekly Stats Fetch")
    print(f"Years: {args.years}")
    print("=" * 60 + "\n")

    env = load_env()
    print("Authenticating...", end=" ", flush=True)
    token = get_token(env)
    print("OK")
    token_time = time.time()

    existing = load_existing()
    existing_keys = {(w["year"], w["week"]) for w in existing["weeks"]}
    print(f"Existing entries: {len(existing_keys)}\n")

    total_fetched = 0
    total_skipped = 0

    for year in args.years:
        print(f"Year {year}:")
        year_fetched = 0

        for week in range(1, WEEKS_PER_YEAR + 1):
            if (year, week) in existing_keys:
                total_skipped += 1
                continue

            # Refresh token if needed
            if time.time() - token_time > TOKEN_TTL:
                print("  Refreshing token...", end=" ", flush=True)
                token = get_token(env)
                token_time = time.time()
                print("OK")

            try:
                localities = fetch_week(token, year, week)
                if localities is None:
                    # Week does not exist (future or gap)
                    break

                stats = compute_stats(localities)
                entry = {"year": year, "week": week, **stats}
                existing["weeks"].append(entry)
                existing_keys.add((year, week))
                year_fetched += 1
                total_fetched += 1

                print(f"  W{week:02d}: {len(localities)} localities, avgLice={stats['avgLice']}, aboveLimit={stats['aboveLimit']}")

            except requests.HTTPError as e:
                if e.response.status_code == 404:
                    print(f"  W{week:02d}: not found, stopping year")
                    break
                print(f"  W{week:02d}: HTTP error {e.response.status_code}, skipping")

            except Exception as e:
                print(f"  W{week:02d}: error - {e}, skipping")

            time.sleep(DELAY)

        print(f"  -> {year_fetched} weeks fetched\n")

    save(existing)
    print(f"\nDone. Fetched {total_fetched} new weeks, skipped {total_skipped} existing.")

if __name__ == "__main__":
    main()
