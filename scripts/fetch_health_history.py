"""
=============================================================================
LAKSATLAS — Barentswatch Health History Fetcher (Fixed)
=============================================================================
Fetches yearly health summaries from Barentswatch Fishhealth API.

Only needs 1 API call per year (the week 52 summary contains all
annual cumulative data including weekly breakdowns).

Run: python scripts/fetch_health_history.py
Output: data/health_history.json
=============================================================================
"""

import requests
import json
import time
from datetime import datetime
from pathlib import Path

# =============================================================================
# SECTION 1: CONFIGURATION
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
CLIENT_ID = env["CLIENT_ID"]
CLIENT_SECRET = env["CLIENT_SECRET"]
TOKEN_URL = "https://id.barentswatch.no/connect/token"
API_BASE = "https://www.barentswatch.no/bwapi"

# =============================================================================
# SECTION 2: AUTHENTICATION
# =============================================================================

def get_token():
    print("Authenticating...")
    response = requests.post(TOKEN_URL, data={
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope": "api"
    })
    response.raise_for_status()
    print("  ✓ Authenticated\n")
    return response.json()["access_token"]

# =============================================================================
# SECTION 3: FETCH YEARLY SUMMARY
# The week 52 summary endpoint contains ALL annual cumulative data
# =============================================================================

def fetch_year_summary(token, year):
    response = requests.post(
        f"{API_BASE}/v2/geodata/fishhealth/{year}/52",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        },
        json={}
    )
    if response.status_code != 200:
        print(f"    Warning: {year} returned status {response.status_code}")
        return None
    return response.json()

# =============================================================================
# SECTION 4: PARSE SUMMARY INTO CLEAN YEARLY STATS
# =============================================================================

def parse_year(year, data):
    result = {
        "year": year,
        "diseases": {},
        "lice_violations_total": 0,
        "lice_violations_weekly": {},
        "escapes": 0
    }

    # --- DISEASES ---
    annual_disease = data.get("annualDiseaseStatistics", {})
    disease_list = annual_disease.get("diseaseStatistics", [])

    if disease_list:
        for d in disease_list:
            name = d.get("name", "UNKNOWN")
            count = d.get("count", 0)
            result["diseases"][name] = count
    else:
        # Sum from weeklyDiseaseStatistics
        weekly = annual_disease.get("weeklyDiseaseStatistics", {})
        disease_totals = {}
        for week_num, cases in weekly.items():
            if isinstance(cases, list):
                for c in cases:
                    name = c.get("name", "UNKNOWN")
                    count = c.get("count", 0)
                    disease_totals[name] = disease_totals.get(name, 0) + count
        result["diseases"] = disease_totals

    # --- LICE VIOLATIONS ---
    annual_lice = data.get("annualLiceStatistics", {})
    lice_stats = annual_lice.get("liceStatistics", {})

    if isinstance(lice_stats, dict):
        result["lice_violations_total"] = lice_stats.get("aboveThreshold", 0)

    weekly_lice = annual_lice.get("weeklyLiceStatistics", {})
    for week_num, stats in weekly_lice.items():
        if isinstance(stats, dict):
            result["lice_violations_weekly"][week_num] = stats.get("aboveThreshold", 0)

    # --- LICE SNAPSHOT WEEK 52 ---
    lice_now = data.get("liceStatistics", {})
    if isinstance(lice_now, dict):
        result["lice_week52"] = {
            "above": lice_now.get("aboveThreshold", {}).get("count", 0),
            "below": lice_now.get("belowThreshold", {}).get("count", 0),
            "below_minimum": lice_now.get("belowMinimumThreshold", {}).get("count", 0)
        }

    # --- ESCAPES ---
    annual_escapes = data.get("annualEscapeStatistics", {})
    if isinstance(annual_escapes, dict):
        escape_stats = annual_escapes.get("escapeStatistics", [])
        if isinstance(escape_stats, list):
            for es in escape_stats:
                if isinstance(es, dict):
                    result["escapes"] += es.get("count", 0)
        if result["escapes"] == 0:
            weekly_esc = annual_escapes.get("weeklyEscapeStatistics", {})
            if isinstance(weekly_esc, dict):
                for week_num, esc_list in weekly_esc.items():
                    if isinstance(esc_list, list):
                        for e in esc_list:
                            if isinstance(e, dict):
                                result["escapes"] += e.get("count", 0)

    return result

# =============================================================================
# SECTION 5: MAIN
# =============================================================================

def main():
    print("=" * 60)
    print("LAKSATLAS — Health History Fetch")
    print("=" * 60 + "\n")

    token = get_token()
    current_year = datetime.now().year
    results = []

    for year in range(2012, current_year + 1):
        print(f"  Fetching {year}...", end=" ")
        try:
            data = fetch_year_summary(token, year)
            time.sleep(0.5)

            if data is None:
                print("FAILED")
                continue

            parsed = parse_year(year, data)
            results.append(parsed)

            diseases_str = ", ".join(f"{k}={v}" for k, v in parsed["diseases"].items())
            print(f"OK — Diseases: [{diseases_str}] | Lice viol: {parsed['lice_violations_total']} | Escapes: {parsed['escapes']}")

        except Exception as e:
            print(f"ERROR: {e}")

    # Save
    data_dir = Path(__file__).parent.parent / "data"
    data_dir.mkdir(exist_ok=True)
    output = {
        "fetched_at": datetime.now().isoformat(),
        "source": "Barentswatch Fishhealth API v2",
        "note": "INFEKSIOES_LAKSEANEMI=ISA, PANKREASSYKDOM=PD",
        "years": results
    }

    filepath = data_dir / "health_history.json"
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*60}")
    print(f"{'Year':<6} {'ISA':>5} {'PD':>5} {'Other':>7} {'Lice viol':>10} {'Escapes':>8}")
    print("-" * 48)
    for r in results:
        isa = r["diseases"].get("INFEKSIOES_LAKSEANEMI", 0)
        pd_ = r["diseases"].get("PANKREASSYKDOM", 0)
        other = sum(v for k, v in r["diseases"].items() if k not in ["INFEKSIOES_LAKSEANEMI", "PANKREASSYKDOM"])
        print(f"{r['year']:<6} {isa:>5} {pd_:>5} {other:>7} {r['lice_violations_total']:>10} {r['escapes']:>8}")

    print(f"\n✓ Saved to {filepath}")
    print("=" * 60)

if __name__ == "__main__":
    main()
