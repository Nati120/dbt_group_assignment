"""City Comfort Index dashboard.

Reads from the final dbt mart models in weather.duckdb (not the raw CSVs).
Run from the project root:

    streamlit run streamlit_app/app.py
"""

from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st

# weather.duckdb lives in the project root (one level up from this file).
DB_PATH = Path(__file__).resolve().parents[1] / "weather.duckdb"

st.set_page_config(page_title="City Comfort Index", layout="wide")
st.title("🌤️ City Comfort Index")
st.caption(
    "Main model **fct_city_weather_day** — grain: one row per city per day. "
    "**comfort_score** is a weighted 0–100 daily index "
    "(temperature 40%, precipitation 25%, air quality 20%, wind 15%); "
    "the City Comfort Index is its average per city."
)


@st.cache_data
def load_data():
    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        summary = con.execute("select * from mart_city_comfort_summary").df()
        daily = con.execute(
            """
            select f.*, d.city_name
            from fct_city_weather_day as f
            join dim_location as d using (location_id)
            """
        ).df()
        locations = con.execute("select * from dim_location").df()
    finally:
        con.close()
    daily["weather_date"] = pd.to_datetime(daily["weather_date"])
    return summary, daily, locations


if not DB_PATH.exists():
    st.error(
        f"Could not find {DB_PATH.name}. Run the extraction, load, and dbt build first "
        "(see the README)."
    )
    st.stop()

summary, daily, locations = load_data()

# --- Filters ---
all_cities = sorted(summary["city_name"].dropna().unique())
cities = st.sidebar.multiselect("Cities", all_cities, default=all_cities)

min_date = daily["weather_date"].min().date()
max_date = daily["weather_date"].max().date()
date_range = st.sidebar.date_input(
    "Date range", value=(min_date, max_date), min_value=min_date, max_value=max_date
)

summary_f = summary[summary["city_name"].isin(cities)]
daily_f = daily[daily["city_name"].isin(cities)]
if isinstance(date_range, tuple) and len(date_range) == 2:
    start, end = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
    daily_f = daily_f[(daily_f["weather_date"] >= start) & (daily_f["weather_date"] <= end)]

# --- KPIs ---
col1, col2, col3 = st.columns(3)
col1.metric("Cities", len(summary_f))
col2.metric("Avg comfort score", round(summary_f["comfort_score"].mean(), 1) if len(summary_f) else 0)
col3.metric("Comfortable days", int(summary_f["comfortable_days"].sum()) if len(summary_f) else 0)

# --- Chart 1: ranking ---
st.subheader("City ranking by comfort score")
ranked = summary_f.sort_values("comfort_score", ascending=False)
display_cols = [c for c in ranked.columns if c != "location_id"]
st.dataframe(ranked[display_cols], use_container_width=True, hide_index=True)
if len(ranked):
    st.bar_chart(ranked.set_index("city_name")["comfort_score"])

# --- Chart 2: map of selected cities ---
st.subheader("Selected cities")
map_df = (
    locations[locations["city_name"].isin(cities)][["latitude", "longitude"]]
    .rename(columns={"latitude": "lat", "longitude": "lon"})
    .dropna()
)
if len(map_df):
    st.map(map_df)

# --- Chart 3: daily mean temperature trend ---
st.subheader("Daily mean temperature (°C)")
if len(daily_f):
    pivot = daily_f.pivot_table(index="weather_date", columns="city_name", values="temp_mean_c")
    st.line_chart(pivot)

# --- Chart 4: daily comfort score timeline ---
st.subheader("Daily comfort score timeline")
if len(daily_f):
    pivot_comfort = daily_f.pivot_table(index="weather_date", columns="city_name", values="comfort_score")
    st.line_chart(pivot_comfort)
