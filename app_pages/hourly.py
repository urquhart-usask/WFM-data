"""Hourly observations page — web equivalent of wfm-fetch.py."""

import csv
import io
from datetime import date, timedelta

import streamlit as st

from wfm_core import COLUMNS, KNOWN_STATIONS, fetch_range

st.title("Hourly observations")
st.caption(
    "Fetches hourly observations from wfm.gov.sk.ca for a station and "
    "date range, and serves the result as a CSV download. "
    "For map locations see "
    "[map](https://www.google.com/maps/d/viewer?mid=1eW3c60_puJdNp8DtBe_Nx386gOIVSsI&femb=1&ll=58.1293829607758%2C-96.73329985&z=3)."
)


station_choice = st.selectbox("Station", KNOWN_STATIONS + ["Other..."])
if station_choice == "Other...":
    station = st.text_input("Station code").strip().upper()
else:
    station = station_choice

col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("Start date", value=date.today() - timedelta(days=30))
with col2:
    end_date = st.date_input("End date", value=date.today())

if st.button("Fetch data", type="primary", disabled=not station):
    if end_date < start_date:
        st.error("End date is before start date.")
    else:
        progress = st.progress(0.0, text="Starting...")
        rows, warnings = fetch_range(
            station,
            start_date,
            end_date,
            on_window=lambda anchor, done, total: progress.progress(
                done / total, text=f"Fetching window anchored at {anchor} ..."
            ),
        )
        progress.empty()

        for warning in warnings:
            st.warning(warning)

        if not rows:
            st.error("No data retrieved. Check the station code and date range.")
        else:
            st.session_state["hourly_rows"] = rows
            st.session_state["hourly_label"] = (
                f"{station}_{start_date.isoformat()}_{end_date.isoformat()}"
            )

# Results persist in session_state so they survive the rerun triggered
# by clicking the download button.
if "hourly_rows" in st.session_state:
    rows = st.session_state["hourly_rows"]
    label = st.session_state["hourly_label"]

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=COLUMNS)
    writer.writeheader()
    writer.writerows(rows)

    st.success(f"Retrieved {len(rows)} rows.")
    st.download_button(
        "Download CSV",
        data=buf.getvalue(),
        file_name=f"{label}.csv",
        mime="text/csv",
    )
    st.dataframe(rows, use_container_width=True)
