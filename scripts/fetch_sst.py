"""
Fetch monthly sea surface temperature (SST) from NOAA OISST v2.1 via ERDDAP.
Outputs data/sea_temperature.json — run monthly to keep data current.

Usage:
    python scripts/fetch_sst.py
"""

import csv, json, math, sys, io
from datetime import date
from urllib.request import urlopen
from urllib.error import URLError, HTTPError

ERDDAP_BASE = (
    "https://coastwatch.pfeg.noaa.gov/erddap/griddap/"
    "ncdcOisst21Agg_LonPM180.csv"
)
# Stride 4 at 0.25° native resolution = 1° output grid (180×360 = 64 800 pts)
STRIDE = 4
LAT_START, LAT_END = -89.875, 89.875
LON_START, LON_END = -179.875, 179.875
OUT_PATH = "data/sea_temperature.json"


def prev_month_15(ref=None):
    """Return the 15th of the month before `ref` (defaults to today)."""
    ref = ref or date.today()
    if ref.month == 1:
        return date(ref.year - 1, 12, 15)
    return date(ref.year, ref.month - 1, 15)


def build_url(target_date):
    ts = target_date.strftime("%Y-%m-%dT12:00:00Z")
    # ERDDAP griddap: coordinate values must be wrapped in () when using stride
    return (
        f"{ERDDAP_BASE}?sst[({ts}):1:({ts})][0:1:0]"
        f"[({LAT_START}):{STRIDE}:({LAT_END})]"
        f"[({LON_START}):{STRIDE}:({LON_END})]"
    )


def fetch_month(target_date):
    url = build_url(target_date)
    print(f"  Fetching {target_date} …", flush=True)
    try:
        with urlopen(url, timeout=120) as resp:
            raw = resp.read().decode("utf-8")
    except HTTPError as e:
        print(f"  HTTP {e.code}: {e.reason}")
        return None
    except URLError as e:
        print(f"  Network error: {e.reason}")
        return None

    reader = csv.reader(io.StringIO(raw))
    next(reader)  # column names
    next(reader)  # units row

    rows = []
    for r in reader:
        try:
            lat = float(r[2])
            lon = float(r[3])
            sst_raw = r[4].strip()
            sst = None if sst_raw in ("", "NaN", "nan") else round(float(sst_raw), 1)
            rows.append((lat, lon, sst))
        except (ValueError, IndexError):
            continue

    return rows


def build_grid(rows):
    lats = sorted(set(r[0] for r in rows))
    lons = sorted(set(r[1] for r in rows))
    if len(lats) < 2 or len(lons) < 2:
        raise ValueError("Too few unique lat/lon values — data may be corrupt.")

    lat0, lon0 = lats[0], lons[0]
    dlat = round(lats[1] - lats[0], 6)
    dlon = round(lons[1] - lons[0], 6)
    nlat, nlon = len(lats), len(lons)

    flat = [None] * (nlat * nlon)
    for lat, lon, sst in rows:
        li = round((lat - lat0) / dlat)
        loi = round((lon - lon0) / dlon)
        if 0 <= li < nlat and 0 <= loi < nlon:
            flat[li * nlon + loi] = sst

    return {
        "lat0": lat0, "lon0": lon0,
        "dlat": dlat, "dlon": dlon,
        "nlat": nlat, "nlon": nlon,
        "sst":  flat,
    }


def main():
    target = prev_month_15()

    # Try up to 4 months back if latest isn't available yet
    rows = None
    for attempt in range(4):
        if attempt > 0:
            m = target.month - attempt
            y = target.year
            while m < 1:
                m += 12
                y -= 1
            target = date(y, m, 15)

        rows = fetch_month(target)
        if rows:
            break
        print(f"  No data for {target}, trying earlier month…")

    if not rows:
        print("ERROR: Could not fetch SST data for any of the attempted months.", file=sys.stderr)
        sys.exit(1)

    print(f"  Received {len(rows):,} data points.")
    grid = build_grid(rows)
    non_null = sum(1 for v in grid["sst"] if v is not None)
    print(f"  Grid: {grid['nlat']}×{grid['nlon']}  ({non_null:,} ocean cells, "
          f"{grid['nlat']*grid['nlon']-non_null:,} land/ice)")

    out = {"month": target.strftime("%Y-%m"), **grid}

    with open(OUT_PATH, "w") as f:
        json.dump(out, f, separators=(",", ":"))

    size_kb = len(json.dumps(out, separators=(",", ":"))) // 1024
    print(f"  Saved -> {OUT_PATH}  ({size_kb} KB)")


if __name__ == "__main__":
    main()
