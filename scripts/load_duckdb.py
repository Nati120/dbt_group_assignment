#!/usr/bin/env python3
"""Load the extracted Open-Meteo CSV files into DuckDB as raw source tables.

Run this AFTER scripts/extract_open_meteo.py has written the CSVs to
data/raw/open_meteo/. It creates (or replaces) one table per CSV in the
DuckDB file that dbt reads from. dbt sources point at these tables.

    uv run python scripts/load_duckdb.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

import duckdb

# table name in DuckDB -> CSV file name
RAW_TABLES = {
    "raw_locations": "raw_locations.csv",
    "raw_weather_daily": "raw_weather_daily.csv",
    "raw_forecast_daily": "raw_forecast_daily.csv",
    "raw_air_quality_hourly": "raw_air_quality_hourly.csv",
}


def load(db_path: str, raw_dir: str) -> None:
    raw_path = Path(raw_dir)
    con = duckdb.connect(db_path)
    try:
        for table, filename in RAW_TABLES.items():
            csv_path = raw_path / filename
            if not csv_path.exists() or csv_path.stat().st_size == 0:
                print(f"Skipping {table}: {csv_path} is missing or empty.")
                continue
            con.execute(
                f"create or replace table {table} as "
                "select * from read_csv_auto(?, header=true)",
                [str(csv_path)],
            )
            count = con.execute(f"select count(*) from {table}").fetchone()[0]
            print(f"Loaded {table}: {count:,} rows")
    finally:
        con.close()
    print(f"Database written to {Path(db_path).resolve()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Load Open-Meteo CSV files into DuckDB raw tables."
    )
    parser.add_argument("--database", "-d", default="weather.duckdb")
    parser.add_argument("--raw-dir", default="data/raw/open_meteo")
    args = parser.parse_args()
    load(args.database, args.raw_dir)
