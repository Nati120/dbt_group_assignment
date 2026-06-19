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
    "A data-driven ranking of city weather comfort based on observed meteorological "
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
        daily = con.execute(
            """
            select f.*, d.city_name, d.country
            from fct_city_weather_day as f
            join dim_location as d using (location_id)
            """
        ).df()
        locations = con.execute("select * from dim_location").df()
        forecast = con.execute(
            """
            select f.*, d.city_name
            from fct_forecast_city_day as f
            join dim_location as d using (location_id)
            """
        ).df()
    finally:
        con.close()
    daily["weather_date"] = pd.to_datetime(daily["weather_date"])
    forecast["forecast_date"] = pd.to_datetime(forecast["forecast_date"])
    return daily, locations, forecast


def compute_summary(daily_df):
    """Aggregate daily fact rows into a per-city summary respecting any active filters."""
    return (
        daily_df.groupby(["city_name", "country"])
        .agg(
            total_days=("weather_date", "count"),
            avg_temp_c=("temp_mean_c", "mean"),
            comfortable_days=("is_comfortable", "sum"),
            rainy_days=("is_rainy", "sum"),
            windy_days=("is_windy", "sum"),
            hot_days=("is_hot", "sum"),
            avg_aqi=("avg_european_aqi", "mean"),
            comfort_score=("comfort_score", "mean"),
        )
        .round(1)
        .reset_index()
    )


def compute_forecast_comfort(df):
    """Estimate comfort score from forecast data (no AQI available)."""
    # Temperature score: peaks at 22C, penalised above 30C max
    temp_score = (100 - (df["temp_mean_c"] - 22).abs() * 5).clip(0, 100)
    heat_penalty = ((df["temp_max_c"] - 30).clip(lower=0) * 3).clip(0, 100)
    temp_score = (temp_score - heat_penalty).clip(0, 100)

    # Precipitation score
    precip_score = (100 - df["precipitation_mm"] * 10).clip(0, 100)

    # Wind score
    wind_score = (100 - (df["wind_speed_max_kmh"] - 15).clip(lower=0) * 3).clip(0, 100)

    # Weighted score without AQI — renormalise weights: temp 50%, precip 30%, wind 20%
    comfort = (temp_score * 0.50 + precip_score * 0.30 + wind_score * 0.20).round(1)
    return comfort


if not DB_PATH.exists():
    st.error(
        f"Could not find {DB_PATH.name}. Run the extraction, load, and dbt build first "
        "(see the README)."
    )
    st.stop()

daily, locations, forecast = load_data()

# --- Filters ---
st.sidebar.header("Filters")
all_cities = sorted(daily["city_name"].dropna().unique())
cities = st.sidebar.multiselect("Cities", all_cities, default=all_cities)

min_date = daily["weather_date"].min().date()
max_date = daily["weather_date"].max().date()
date_range = st.sidebar.date_input(
    "Date range", value=(min_date, max_date), min_value=min_date, max_value=max_date
)

daily_f = daily[daily["city_name"].isin(cities)]
if isinstance(date_range, tuple) and len(date_range) == 2:
    start, end = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
    daily_f = daily_f[(daily_f["weather_date"] >= start) & (daily_f["weather_date"] <= end)]

# Summary computed dynamically from filtered daily data — always reflects active filters
summary_f = compute_summary(daily_f)

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
ranked_display = ranked.rename(columns={
    "city_name": "City",
    "country": "Country",
    "total_days": "Days analyzed",
    "avg_temp_c": "Avg temp (°C)",
    "comfortable_days": "Comfortable days",
    "rainy_days": "Rainy days",
    "windy_days": "Windy days",
    "hot_days": "Hot days",
    "avg_aqi": "Avg AQI",
    "comfort_score": "Comfort score",
})
st.dataframe(ranked_display, use_container_width=True, hide_index=True)

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
    daily_f_plot = daily_f.copy()
    daily_f_plot["weather_date"] = daily_f_plot["weather_date"].dt.date
    pivot = daily_f_plot.pivot_table(index="weather_date", columns="city_name", values="temp_mean_c")
    st.line_chart(pivot)

# --- Comfort score timeline ---
st.subheader("Daily comfort score timeline")
st.caption(
    "Day-by-day comfort score per city. Dips typically correspond to rainy, hot, or windy days. "
    "Compare this with the temperature chart above to identify the main drivers of discomfort."
)
if len(daily_f):
    daily_f_plot2 = daily_f.copy()
    daily_f_plot2["weather_date"] = daily_f_plot2["weather_date"].dt.date
    pivot_comfort = daily_f_plot2.pivot_table(index="weather_date", columns="city_name", values="comfort_score")
    st.line_chart(pivot_comfort)

st.divider()

# --- Forecast panel ---
st.subheader("7-day forecast comfort")
st.caption(
    "Estimated comfort score for the next 7 days based on the weather forecast. "
    "Air quality is not included in forecast data, so weights are redistributed: "
    "temperature 50%, precipitation 30%, wind 20%."
)
forecast_f = forecast[forecast["city_name"].isin(cities)].copy()
if len(forecast_f):
    forecast_f["forecast_date"] = pd.to_datetime(forecast_f["forecast_date"]).dt.strftime("%b %d")
    pivot_forecast = forecast_f.groupby(["forecast_date", "city_name"])["comfort_score_est"].mean().unstack("city_name")
    st.line_chart(pivot_forecast)

    st.caption("Forecast summary by city")
    forecast_summary = (
        forecast_f.groupby("city_name")
        .agg(
            avg_temp_c=("temp_mean_c", "mean"),
            total_precip_mm=("precipitation_mm", "sum"),
            avg_wind_kmh=("wind_speed_max_kmh", "mean"),
            est_comfort_score=("comfort_score_est", "mean"),
        )
        .round(1)
        .reset_index()
        .sort_values("est_comfort_score", ascending=False)
        .rename(columns={
            "city_name": "City",
            "avg_temp_c": "Avg temp (°C)",
            "total_precip_mm": "Total precip (mm)",
            "avg_wind_kmh": "Avg wind (km/h)",
            "est_comfort_score": "Est. comfort score",
        })
    )
    st.dataframe(forecast_summary, use_container_width=True, hide_index=True)
