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
st.title("City Comfort Index")
st.markdown(
    "A data-driven ranking of city weather comfort based on 31 days of observed meteorological "
    "and air quality data from the Open-Meteo API. Use the filters on the left to explore by city and date range."
)

with st.expander("How is the comfort score calculated?"):
    st.markdown(
        """
        Each day receives a **comfort score from 0 to 100** built from four weighted components:

        | Component | Weight | Logic |
        |---|---|---|
        | Temperature | **40%** | Peaks at 22 °C mean temp; penalised when daily max exceeds 30 °C |
        | Precipitation | **25%** | 100 for a dry day; drops 10 pts per mm of rain |
        | Air quality | **20%** | Based on the European AQI — 100 = clean air, 0 = very poor |
        | Wind | **15%** | 100 for calm conditions; penalised above 15 km/h |

        A day is flagged **comfortable** when mean temp is 18–26 °C, precipitation < 1 mm, and max wind < 25 km/h.
        When air quality data is unavailable, the remaining weights are renormalised so no city is unfairly penalised.

        The **City Comfort Index** is the average daily comfort score over the selected period.

        *Source model: `fct_city_weather_day` — grain: one row per city per day.*
        """
    )

st.divider()


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
st.sidebar.header("Filters")
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
col1.metric("Cities selected", len(summary_f))
col2.metric("Avg comfort score", round(summary_f["comfort_score"].mean(), 1) if len(summary_f) else 0)
col3.metric("Total comfortable days", int(summary_f["comfortable_days"].sum()) if len(summary_f) else 0)

st.divider()

# --- Ranking table ---
st.subheader("City ranking by comfort score")
st.caption(
    "Cities ranked from highest to lowest comfort score over the selected period. "
    "Comfortable days are days where all three thresholds (temperature, precipitation, wind) were met simultaneously."
)
ranked = summary_f.sort_values("comfort_score", ascending=False)
display_cols = [c for c in ranked.columns if c != "location_id"]
st.dataframe(ranked[display_cols], use_container_width=True, hide_index=True)

st.subheader("Comfort score by city")
st.caption("Average comfort score per city. Higher is better (scale: 0–100).")
if len(ranked):
    st.bar_chart(ranked.set_index("city_name")["comfort_score"])

st.divider()

# --- Map ---
st.subheader("Selected cities")
st.caption("Geographic location of the cities included in the analysis.")
map_df = (
    locations[locations["city_name"].isin(cities)][["latitude", "longitude"]]
    .rename(columns={"latitude": "lat", "longitude": "lon"})
    .dropna()
)
if len(map_df):
    st.map(map_df)

st.divider()

# --- Temperature trend ---
st.subheader("Daily mean temperature (°C)")
st.caption(
    "Day-by-day mean temperature per city. Useful for spotting heat waves or cold spells "
    "that may have driven down comfort scores."
)
if len(daily_f):
    pivot = daily_f.pivot_table(index="weather_date", columns="city_name", values="temp_mean_c")
    st.line_chart(pivot)

# --- Comfort score timeline ---
st.subheader("Daily comfort score timeline")
st.caption(
    "Day-by-day comfort score per city. Dips typically correspond to rainy, hot, or windy days. "
    "Compare this with the temperature chart above to identify the main drivers of discomfort."
)
if len(daily_f):
    pivot_comfort = daily_f.pivot_table(index="weather_date", columns="city_name", values="comfort_score")
    st.line_chart(pivot_comfort)
