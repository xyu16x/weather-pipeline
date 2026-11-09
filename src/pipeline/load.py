"""data/raw/*.json を DuckDB の raw.weather_hourly にロードする。

主キー (location, observed_at) で INSERT OR REPLACE するので、何度実行しても結果は同じ(冪等)。
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import duckdb

DDL = """
CREATE SCHEMA IF NOT EXISTS raw;
CREATE TABLE IF NOT EXISTS raw.weather_hourly (
    location       VARCHAR   NOT NULL,
    observed_at    TIMESTAMP NOT NULL,   -- Asia/Tokyo のローカル時刻
    temperature_2m DOUBLE,
    precipitation  DOUBLE,
    wind_speed_10m DOUBLE,
    source_file    VARCHAR,
    loaded_at      TIMESTAMP DEFAULT current_timestamp,
    PRIMARY KEY (location, observed_at)
);
"""


def parse_rows(payload: dict, source_file: str) -> list[tuple]:
    hourly = payload["hourly"]
    times = hourly["time"]
    for key in ("temperature_2m", "precipitation", "wind_speed_10m"):
        if len(hourly[key]) != len(times):
            raise ValueError(f"length mismatch: {key}")
    return [
        (
            payload["location"],
            times[i],
            hourly["temperature_2m"][i],
            hourly["precipitation"][i],
            hourly["wind_speed_10m"][i],
            source_file,
        )
        for i in range(len(times))
    ]


def load_files(con: duckdb.DuckDBPyConnection, files: list[Path]) -> int:
    con.execute(DDL)
    total = 0
    for f in files:
        payload = json.loads(f.read_text(encoding="utf-8"))
        rows = parse_rows(payload, f.name)
        con.executemany(
            "INSERT OR REPLACE INTO raw.weather_hourly "
            "(location, observed_at, temperature_2m, precipitation, wind_speed_10m, source_file) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            rows,
        )
        total += len(rows)
    return total


def main() -> None:
    import argparse

    from .fetch import fetch_all

    p = argparse.ArgumentParser(description="Open-Meteo -> DuckDB")
    p.add_argument("--days", type=int, default=7, help="何日分さかのぼるか (アーカイブは数日遅延あり)")
    p.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    p.add_argument("--db", type=Path, default=Path("data/weather.duckdb"))
    p.add_argument("--skip-fetch", action="store_true", help="既存の raw JSON だけロード")
    args = p.parse_args()

    if not args.skip_fetch:
        end = date.today() - timedelta(days=5)  # 確定値が出るまでの遅延を見込む
        start = end - timedelta(days=args.days - 1)
        fetch_all(start, end, args.raw_dir)

    args.db.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(args.db))
    n = load_files(con, sorted(args.raw_dir.glob("*.json")))
    print(f"loaded {n} rows into {args.db}")


if __name__ == "__main__":
    main()
