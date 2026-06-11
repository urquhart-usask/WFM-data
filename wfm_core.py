"""
wfm_core.py

Shared fetch logic for the WFM Streamlit app pages. Mirrors the logic in
wfm-fetch.py / wfm-rainfall.py but UI-agnostic: no printing, no Streamlit.
"""

import json
import re
import ssl
import time
import urllib.error
import urllib.request
from datetime import date, timedelta

BASE_URL = "https://wfm.gov.sk.ca/wfm/table/stn/data"

KNOWN_STATIONS = ["CNDLK", "WGULL", "STURT", "LBEAR"]

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


def _get(url: str) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read().decode("utf-8")
    except urllib.error.URLError as exc:
        if not isinstance(exc.reason, ssl.SSLError):
            raise
        # wfm.gov.sk.ca has previously served a self-signed certificate;
        # fall back to an unverified connection if verification fails.
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
            return resp.read().decode("utf-8")


def fetch_window(station: str, anchor_date: date) -> list[dict]:
    """
    Fetch the ~3-day observation window for a given anchor date.
    Returns a list of row dicts keyed by COLUMNS. Raises on request or
    parse failure.
    """
    url = (
        f"{BASE_URL}"
        f"?stn={station}"
        f"&date={anchor_date.isoformat()}"
        f"&typ=today"
        f"&dtype=hourly"
        f"&tqx=reqId%3A0"
    )

    raw = _get(url)

    match = re.search(r'setResponse\((\{.*\})\)', raw, re.DOTALL)
    if not match:
        raise ValueError("unexpected response format")

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


def window_count(start: date, end: date) -> int:
    """Number of 3-day windows fetch_range will request for this range."""
    days = (end - start).days
    return 1 if days <= 0 else -(-days // 3) + 1


def fetch_range(
    station: str,
    start: date,
    end: date,
    on_window=None,
) -> tuple[list[dict], list[str]]:
    """
    Step through the date range in 3-day increments, deduplicating by
    valid_time and filtering to the requested window.

    on_window, if given, is called as on_window(anchor_date, done, total)
    before each request — used for progress reporting.

    Returns (rows, warnings): rows sorted chronologically, and a list of
    human-readable warnings for windows that failed.
    """
    seen = {}
    warnings = []
    current = start
    total = window_count(start, end)
    done = 0

    while True:
        if on_window:
            on_window(current, done, total)
        try:
            rows = fetch_window(station, current)
        except Exception as exc:
            warnings.append(f"{station} {current}: {exc}")
            rows = []

        for row in rows:
            key = row["valid_time"]
            if key and key not in seen:
                seen[key] = row

        done += 1
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

    return filtered, warnings


def daily_rain_totals(rows: list[dict]) -> dict[str, float]:
    """
    Sum hourly rainfall (mm) from fetch_range rows into per-calendar-day
    totals. Blank/missing readings are treated as 0.
    """
    totals = {}
    for row in rows:
        day = row["valid_time"][:10]
        rain = row["rain_1hr_mm"]
        amount = float(rain) if rain not in ("", None) else 0.0
        totals[day] = totals.get(day, 0.0) + amount
    return totals
