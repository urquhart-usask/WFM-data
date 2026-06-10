"""
wfm_fetch.py

Fetches hourly weather observations from the Saskatchewan Wildfire
Weather Monitoring network (wfm.gov.sk.ca) for a given station and
date range, and writes the result to a CSV file.

The API returns a rolling ~3-day window anchored to the requested date.
This script steps forward in 3-day increments, deduplicates rows by
timestamp, sorts chronologically, and writes a single clean CSV.

Configure STATION, START_DATE, and END_DATE below, then run directly
in PyCharm (Run > Run 'wfm_fetch').
"""

import csv
import json
import re
import sys
import time
import urllib.request
from datetime import date, timedelta

# ---------------------------------------------------------------------------
# Configuration — edit these three values before running
# ---------------------------------------------------------------------------



STATION = ("WGULL")
#STATION = ("STURT")
#STATION = ("LBEAR")
#STATION = ("CNDLK")
START_DATE = date(2026, 6, 1)
END_DATE = date.today()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASE_URL = "https://wfm.gov.sk.ca/wfm/table/stn/data"

COLUMNS = [
    "valid_time",
    "temp_c",
    "rh_pct",
    "wind_speed_km_h",
    "wind_gusts_km_h",
    "wind_dir",
    "wind_az_deg",
    "rain_1hr_mm",
    "pressure_hpa",
    "pressure_trend_3h",
    "hourly_ffmc",
    "hourly_isi",
    "hourly_fwi",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://wfm.gov.sk.ca/wfm/table",
    "Accept": "*/*",
}


# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------

def fetch_window(station: str, anchor_date: date) -> list[dict]:
    """
    Fetch the ~3-day observation window for a given anchor date.
    Returns a list of row dicts keyed by COLUMNS.
    """
    url = (
        f"{BASE_URL}"
        f"?stn={station}"
        f"&date={anchor_date.isoformat()}"
        f"&typ=today"
        f"&dtype=hourly"
        f"&tqx=reqId%3A0"
    )

    req = urllib.request.Request(url, headers=HEADERS)

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8")
    except Exception as exc:
        print(f"  Warning: request failed for {anchor_date} - {exc}", file=sys.stderr)
        return []

    match = re.search(r'setResponse\((\{.*\})\)', raw, re.DOTALL)
    if not match:
        print(f"  Warning: unexpected response format for {anchor_date}", file=sys.stderr)
        return []

    outer = json.loads(match.group(1))
    table = json.loads(outer["table"])

    cols = [c["id"] for c in table["cols"]]
    rows = []

    for row in table.get("rows", []):
        cells = row.get("c", [])
        record = {}

        for i, col_id in enumerate(cols):
            cell = cells[i] if i < len(cells) else None
            if cell is None:
                record[col_id] = ""
            elif col_id == "dt":
                record[col_id] = cell.get("f", "")
            else:
                val = cell.get("v", "") if cell else ""
                record[col_id] = "" if val is None else val

        mapped = {
            "valid_time":        record.get("dt", ""),
            "temp_c":            record.get("temp", ""),
            "rh_pct":            record.get("rh", ""),
            "wind_speed_km_h":   record.get("wind_speed", ""),
            "wind_gusts_km_h":   record.get("wind_gusts", ""),
            "wind_dir":          record.get("wind_dir", ""),
            "wind_az_deg":       record.get("wind_az", ""),
            "rain_1hr_mm":       record.get("rain_1", ""),
            "pressure_hpa":      record.get("pressure", ""),
            "pressure_trend_3h": record.get("pres_3h", ""),
            "hourly_ffmc":       record.get("h_ffmc", ""),
            "hourly_isi":        record.get("h_isi", ""),
            "hourly_fwi":        record.get("h_fwi", ""),
        }
        rows.append(mapped)

    return rows


def fetch_range(station: str, start: date, end: date) -> list[dict]:
    """
    Step through the date range in 3-day increments, deduplicating by
    valid_time and filtering to the requested window.
    """
    seen = {}
    current = start

    while True:
        print(f"  Fetching window anchored at {current} ...")
        rows = fetch_window(station, current)
        for row in rows:
            key = row["valid_time"]
            if key and key not in seen:
                seen[key] = row

        if current >= end:
            break
        current = min(current + timedelta(days=3), end)
        time.sleep(0.5)

    all_rows = sorted(seen.values(), key=lambda r: r["valid_time"])

    end_inclusive = (end + timedelta(days=1)).isoformat()
    filtered = [
        r for r in all_rows
        if start.isoformat() <= r["valid_time"][:10] <= end_inclusive[:10]
    ]

    return filtered


def write_csv(rows: list[dict], output_path: str) -> None:
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  Wrote {len(rows)} rows to {output_path}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    if END_DATE < START_DATE:
        print("Error: END_DATE is before START_DATE.")
        sys.exit(1)

    output = f"{STATION}_{START_DATE.isoformat()}_{END_DATE.isoformat()}.csv"

    print(f"Station : {STATION}")
    print(f"Range   : {START_DATE} to {END_DATE}")
    print(f"Output  : {output}")
    print()

    rows = fetch_range(STATION, START_DATE, END_DATE)

    if not rows:
        print("No data retrieved. Check STATION and date range.")
        sys.exit(1)

    write_csv(rows, output)
    print("Done.")


if __name__ == "__main__":
    main()
