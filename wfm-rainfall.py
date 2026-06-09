#!/usr/bin/env python3
"""
wfm_rainfall.py

Fetches the last 7 days of hourly weather observations from the
Saskatchewan Wildfire Weather Monitoring network (wfm.gov.sk.ca) for a
set of stations, sums the hourly rainfall into daily totals per station,
and writes a table to a CSV file with one row per date and one column
per station (station codes as column headers, dates as row labels).

Configure STATIONS and DAYS below, then run directly in PyCharm
(Run > Run 'wfm_rainfall').
"""

import csv
import json
import re
import sys
import time
import urllib.request
from datetime import date, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration — edit these values before running
# ---------------------------------------------------------------------------

STATIONS = ["WGULL", "CNDLK", "STURT", "LBEAR"]
DAYS = 7
CSV_WRITE = True
OUTPUT_DIR = Path.home() / "Documents"
END_DATE = date.today()
START_DATE = END_DATE - timedelta(days=DAYS - 1)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASE_URL = "https://wfm.gov.sk.ca/wfm/table/stn/data"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://wfm.gov.sk.ca/wfm/table",
    "Accept": "*/*",
}

OUTPUT_COLUMNS = ["date"] + STATIONS


# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------

def fetch_window(station: str, anchor_date: date) -> list[tuple[str, str]]:
    """
    Fetch the ~3-day observation window for a given anchor date.
    Returns a list of (valid_time, rain_1hr_mm) pairs.
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
        print(f"  Warning: request failed for {station} {anchor_date} - {exc}", file=sys.stderr)
        return []

    match = re.search(r'setResponse\((\{.*\})\)', raw, re.DOTALL)
    if not match:
        print(f"  Warning: unexpected response format for {station} {anchor_date}", file=sys.stderr)
        return []

    outer = json.loads(match.group(1))
    table = json.loads(outer["table"])

    cols = [c["id"] for c in table["cols"]]
    pairs = []

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

        pairs.append((record.get("dt", ""), record.get("rain_1", "")))

    return pairs


def fetch_hourly_rain(station: str, start: date, end: date) -> dict[str, str]:
    """
    Step through the date range in 3-day increments — always landing the
    final query on `end` so the freshest data is captured — deduplicate by
    timestamp, and return {valid_time: rain_1hr_mm} restricted to the window.
    """
    seen = {}
    current = start

    while True:
        print(f"  [{station}] Fetching window anchored at {current} ...")
        for valid_time, rain in fetch_window(station, current):
            if valid_time and valid_time not in seen:
                seen[valid_time] = rain

        if current >= end:
            break
        current = min(current + timedelta(days=3), end)
        time.sleep(0.5)

    end_inclusive = (end + timedelta(days=1)).isoformat()
    return {
        valid_time: rain
        for valid_time, rain in seen.items()
        if start.isoformat() <= valid_time[:10] <= end_inclusive[:10]
    }


def daily_totals(hourly_rain: dict[str, str]) -> dict[str, float]:
    """
    Sum hourly rainfall (mm) into per-calendar-day totals.
    Blank/missing readings are treated as 0.
    """
    totals = {}
    for valid_time, rain in hourly_rain.items():
        day = valid_time[:10]
        amount = float(rain) if rain not in ("", None) else 0.0
        totals[day] = totals.get(day, 0.0) + amount
    return totals


def print_table(rows: list[dict]) -> None:
    col_width = max(10, *(len(s) for s in STATIONS))
    date_width = 10
    header = f"{'Date':<{date_width}}" + "".join(f"  {s:>{col_width}}" for s in STATIONS)
    separator = "-" * len(header)
    print()
    print(header)
    print(separator)
    for row in rows:
        line = f"{row['date']:<{date_width}}"
        for station in STATIONS:
            line += f"  {row[station]:>{col_width}}"
        print(line)
    print(separator)


def write_csv(rows: list[dict], filename: str) -> None:
    output_path = OUTPUT_DIR / filename
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {output_path}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    filename = f"daily_rainfall_{START_DATE.isoformat()}_{END_DATE.isoformat()}.csv"

    print(f"Stations : {', '.join(STATIONS)}")
    print(f"Range    : {START_DATE} to {END_DATE}")
    print()

    by_station = {}
    all_days = set()
    for station in STATIONS:
        hourly_rain = fetch_hourly_rain(station, START_DATE, END_DATE)
        totals = daily_totals(hourly_rain)
        by_station[station] = totals
        all_days.update(totals)

    if not all_days:
        print("No data retrieved. Check STATIONS and date range.")
        sys.exit(1)

    table_rows = []
    for day in sorted(all_days):
        row = {"date": day}
        for station in STATIONS:
            row[station] = round(by_station[station].get(day, 0.0), 1)
        table_rows.append(row)
    print(filename)
    print_table(table_rows)
    if CSV_WRITE:
        write_csv(table_rows, filename)

    print("Done.")


if __name__ == "__main__":
    main()