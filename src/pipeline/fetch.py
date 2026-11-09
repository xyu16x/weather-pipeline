"""Open-Meteo Historical API から時間別気象データを取得し、生JSONのまま保存する。

- API: https://open-meteo.com/en/docs/historical-weather-api (キー不要・非商用)
- データ: CC BY 4.0 (出典表記が必要。README参照)
- 取得したレスポンスは加工せず data/raw/ に保存する (ELTのE/L)。
"""
from __future__ import annotations

import json
import time
from datetime import date
from pathlib import Path

import requests

BASE_URL = "https://archive-api.open-meteo.com/v1/archive"
HOURLY_VARS = ("temperature_2m", "precipitation", "wind_speed_10m")

# name は dbt の seed (location_aliases.csv) で名寄せされる
LOCATIONS = {
    "Tokyo": (35.6895, 139.6917),
    "Osaka": (34.6937, 135.5023),
    "Sapporo": (43.0618, 141.3545),
}


class FetchError(RuntimeError):
    pass


def fetch_hourly(
    lat: float,
    lon: float,
    start: date,
    end: date,
    *,
    session: requests.Session | None = None,
    max_retries: int = 4,
    backoff_sec: float = 1.0,
    timeout: float = 30.0,
) -> dict:
    """1地点・期間分の時間別データを取得する。

    429 / 5xx / 通信エラーは指数バックオフでリトライ。それ以外の4xxは即失敗。
    """
    if end < start:
        raise ValueError("end must be >= start")

    sess = session or requests.Session()
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "hourly": ",".join(HOURLY_VARS),
        "timezone": "Asia/Tokyo",
    }

    last_err: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            resp = sess.get(BASE_URL, params=params, timeout=timeout)
        except requests.RequestException as e:  # 通信エラー
            last_err = e
        else:
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 429 or resp.status_code >= 500:
                last_err = FetchError(f"HTTP {resp.status_code}")
            else:
                raise FetchError(f"HTTP {resp.status_code}: {resp.text[:200]}")
        if attempt < max_retries:
            time.sleep(backoff_sec * (2**attempt))
    raise FetchError(f"giving up after {max_retries + 1} attempts: {last_err}")


def save_raw(payload: dict, location: str, start: date, end: date, out_dir: Path) -> Path:
    """生レスポンスを location を付与して保存する。同名ファイルは上書き(冪等)。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{location.lower()}_{start.isoformat()}_{end.isoformat()}.json"
    path.write_text(
        json.dumps({"location": location, **payload}, ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def fetch_all(start: date, end: date, out_dir: Path) -> list[Path]:
    paths = []
    for name, (lat, lon) in LOCATIONS.items():
        payload = fetch_hourly(lat, lon, start, end)
        paths.append(save_raw(payload, name, start, end, out_dir))
    return paths
