"""data/raw/*.json を DuckDB の raw.weather_hourly にロードする。

主キー (location, observed_at) で INSERT OR REPLACE するので、何度実行しても結果は同じ(冪等)。
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import duckdb


class EmptyTableError(RuntimeError):
    """raw.weather_hourly が空で、差分の起点が決められない。"""


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


def decide_range(con, today: date) -> tuple[date, date] | None:
    """取得期間 (start, end) を返す。取るものがなければ None。"""
    con.execute(DDL)  # 初回でテーブルがなくても落ちないように

    end = today - timedelta(days=5)  # 確定値が出るまでの遅延を見込む

    # 地点ごとの最新日付のうち、一番古いもの
    last = con.execute("""
        select min(max_d) from (
            select max(cast(observed_at as date)) as max_d
            from raw.weather_hourly
            group by location
        )
    """).fetchone()[0]

    if last is None:  # DBが空 = 初回
        raise EmptyTableError(
            "DBが空です。初回は --start と --end で期間を指定してください"
        )
    start = last + timedelta(days=1)  # 続きから

    if start > end:  # もう最新まで取れている
        return None
    return start, end


def main() -> None:
    import argparse

    from .fetch import fetch_all

    p = argparse.ArgumentParser(description="Open-Meteo -> DuckDB")
    p.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    p.add_argument("--db", type=Path, default=Path("data/weather.duckdb"))
    p.add_argument(
        "--skip-fetch", action="store_true", help="既存の raw JSON だけロード"
    )
    p.add_argument(
        "--start",
        type=date.fromisoformat,
        help="取得開始日 (YYYY-MM-DD)。--end と一緒に指定する",
    )
    p.add_argument(
        "--end",
        type=date.fromisoformat,
        help="取得終了日 (YYYY-MM-DD)",
    )
    args = p.parse_args()

    args.db.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(args.db))

    if args.skip_fetch:
        files = sorted(args.raw_dir.glob("*.json"))
    else:
        if args.start is not None and args.end is not None:
            if args.start >= args.end:
                p.error("--start は --end 以前の日付にしてください")
            rng = (args.start, args.end)
        elif args.start is not None or args.end is not None:
            p.error("--start と --end は両方指定してください")
        else:
            try:
                rng = decide_range(con, date.today())
            except EmptyTableError:
                p.error("初回は --start と --end で期間を指定してください")

        if rng is None:
            print("already up to date")
            files = []
        else:
            start, end = rng
            print(f"fetching {start} .. {end}")
            files = fetch_all(start, end, args.raw_dir)

    n = load_files(con, files)
    print(f"loaded {n} rows into {args.db}")


if __name__ == "__main__":
    main()
