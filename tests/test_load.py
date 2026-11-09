import json
from pathlib import Path

import duckdb
import pytest

from pipeline import load

FIXTURE = Path(__file__).parent / "fixtures" / "sample_response.json"


def test_parse_rows():
    rows = load.parse_rows(json.loads(FIXTURE.read_text()), "x.json")
    assert len(rows) == 5
    assert rows[0] == ("Tokyo", "2026-10-01T00:00", 18.0, 0.0, 5.0, "x.json")
    assert rows[4][2] is None  # 欠損は NULL のまま保持


def test_length_mismatch_raises():
    payload = json.loads(FIXTURE.read_text())
    payload["hourly"]["precipitation"].pop()
    with pytest.raises(ValueError):
        load.parse_rows(payload, "x.json")


def test_load_is_idempotent():
    con = duckdb.connect(":memory:")
    load.load_files(con, [FIXTURE])
    load.load_files(con, [FIXTURE])  # 2回目でも増えない
    assert con.execute("select count(*) from raw.weather_hourly").fetchone()[0] == 5
