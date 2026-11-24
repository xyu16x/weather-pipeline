import json
from pathlib import Path

import duckdb
import pytest

from pipeline import load
from datetime import date

FIXTURE = Path(__file__).parent / "fixtures" / "sample_response.json"
ANY_TODAY = date(2026, 10, 10)


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


def test_decide_range_continues_from_last_date():
    con = duckdb.connect(":memory:")
    today = date(2026, 10, 10)
    load.load_files(con, [FIXTURE])

    start, end = load.decide_range(con, today)
    assert start == date(2026, 10, 3)
    assert end == date(2026, 10, 5)


def test_decide_range_empty_raises():
    con = duckdb.connect(":memory:")
    today = date(2026, 10, 10)

    with pytest.raises(load.EmptyTableError):
        load.decide_range(con, today)


def test_decide_range_up_to_date():
    con = duckdb.connect(":memory:")
    today = date(2026, 10, 7)
    load.load_files(con, [FIXTURE])

    assert load.decide_range(con, today) is None


def test_decide_range_uses_oldest_location():
    con = duckdb.connect(":memory:")
    today = date(2026, 10, 10)
    load.load_files(con, [FIXTURE])
    con.execute(
        "insert into raw.weather_hourly (location, observed_at) values ('Osaka', '2026-09-28 00:00')"
    )

    start, end = load.decide_range(con, today)
    assert start == date(2026, 9, 29)
    assert end == date(2026, 10, 5)


def test_decide_range_single_day():
    con = duckdb.connect(":memory:")
    today = date(2026, 10, 8)
    load.load_files(con, [FIXTURE])

    start, end = load.decide_range(con, today)
    assert start == date(2026, 10, 3)
    assert end == date(2026, 10, 3)


def test_resolve_range_single_day():
    con = duckdb.connect(":memory:")
    day = date(2026, 10, 3)

    start, end = load.resolve_range(con, ANY_TODAY, start=day, end=day)
    assert start == day
    assert end == day


def test_resolve_range_reversed_raises():
    con = duckdb.connect(":memory:")
    start, end = date(2026, 10, 10), date(2026, 10, 5)

    with pytest.raises(load.InvalidRangeError):
        load.resolve_range(con, ANY_TODAY, start, end)


@pytest.mark.parametrize(
    "start, end",
    [
        (date(2026, 10, 5), None),
        (None, date(2026, 10, 5)),
    ],
)
def test_resolve_range_only_one_side_raises(start, end):
    con = duckdb.connect(":memory:")

    with pytest.raises(load.InvalidRangeError):
        load.resolve_range(con, ANY_TODAY, start, end)


def test_resolve_range_none_uses_decide_range():
    con = duckdb.connect(":memory:")
    today = date(2026, 10, 10)
    load.load_files(con, [FIXTURE])

    start, end = load.resolve_range(con, today, start=None, end=None)
    assert start == date(2026, 10, 3)
    assert end == date(2026, 10, 5)
