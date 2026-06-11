"""
streamlit_app.py

Web front-end for the Saskatchewan Wildfire Weather Monitoring network
(wfm.gov.sk.ca). Two pages: hourly observations for one station, and
daily rainfall totals across stations.

Run locally:   streamlit run streamlit_app.py
Deploy:        push to GitHub, then create the app on share.streamlit.io
"""

import streamlit as st

st.set_page_config(page_title="SK Wildfire Weather Data", page_icon="🌦️")

pg = st.navigation([
    st.Page("app_pages/hourly.py", title="Hourly data", icon="🌡️", default=True),
    st.Page("app_pages/rainfall.py", title="Daily rainfall", icon="🌧️"),
])
pg.run()