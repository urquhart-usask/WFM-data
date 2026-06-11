"""Daily rainfall page — web equivalent of wfm-rainfall.py."""

import csv
import io
from datetime import date, timedelta

import streamlit as st

from wfm_core import KNOWN_STATIONS, daily_rain_totals, fetch_range, window_count

st.title("Daily rainfall totals")
st.caption(
    "Sums hourly rainfall from wfm.gov.sk.ca into daily totals per "
    "station — one row per date, one column per station. "
    "For map locations see "
    "[map](https://www.google.com/maps/d/viewer?mid=1eW3c60_puJdNp8DtBe_Nx386gOIVSsI&femb=1&ll=58.1293829607758%2C-96.73329985&z=3)."
)

stations = st.multiselect("Stations", KNOWN_STATIONS, default=KNOWN_STATIONS)

col1, col2 = st.columns(2)
with col1:
    days = st.number_input("Days", min_value=1, max_value=60, value=7)
with col2:
    end_date = st.date_input("End date", value=date.today())
start_date = end_date - timedelta(days=days - 1)

st.caption(f"Range: {start_date} to {end_date}")

if st.button("Fetch data", type="primary", disabled=not stations):
    progress = st.progress(0.0, text="Starting...")
    per_station = window_count(start_date, end_date)
    total = per_station * len(stations)

    by_station = {}
    all_days = set()
    all_warnings = []

    for n, station in enumerate(stations):
        rows, warnings = fetch_range(
            station,
            start_date,
            end_date,
            on_window=lambda anchor, done, _t, n=n, s=station: progress.progress(
                (n * per_station + done) / total,
                text=f"[{s}] Fetching window anchored at {anchor} ...",
            ),
        )
        all_warnings.extend(warnings)
        totals = daily_rain_totals(rows)
        by_station[station] = totals
        all_days.update(totals)

    progress.empty()

    for warning in all_warnings:
        st.warning(warning)

    if not all_days:
        st.error("No data retrieved. Check the stations and date range.")
    else:
        table_rows = []
        for day in sorted(all_days):
            row = {"date": day}
            for station in stations:
                row[station] = round(by_station[station].get(day, 0.0), 1)
            table_rows.append(row)

        st.session_state["rain_rows"] = table_rows
        st.session_state["rain_stations"] = stations
        st.session_state["rain_label"] = (
            f"daily_rainfall_{start_date.isoformat()}_{end_date.isoformat()}"
        )

# Results persist in session_state so they survive the rerun triggered
# by clicking the download button.
if "rain_rows" in st.session_state:
    table_rows = st.session_state["rain_rows"]
    label = st.session_state["rain_label"]

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=["date"] + st.session_state["rain_stations"])
    writer.writeheader()
    writer.writerows(table_rows)

    st.success(f"Retrieved {len(table_rows)} days.")
    st.download_button(
        "Download CSV",
        data=buf.getvalue(),
        file_name=f"{label}.csv",
        mime="text/csv",
    )
    st.dataframe(table_rows, use_container_width=True)