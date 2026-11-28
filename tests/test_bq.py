import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import requests

from pipeline import bq

FIXTURE = Path(__file__).parent / "fixtures" / "sample_response.json"
D = date(2026, 10, 1)


def test_read_rows():
    rows = bq.read_rows([FIXTURE])

    assert len(rows) == 5
    assert rows[0][5] == "sample_response.json"


def test_read_rows_multiple_files(tmp_path):
    osaka = json.loads(FIXTURE.read_text())
    osaka["location"] = "Osaka"
    osaka_file = tmp_path / "osaka.json"
    osaka_file.write_text(json.dumps(osaka))

    rows = bq.read_rows([FIXTURE, osaka_file])

    assert len(rows) == 10
    assert rows[0][0] == "Tokyo"  # 1つ目のファイルの行が先
    assert rows[5][0] == "Osaka"  # 2つ目のファイルの行が後
    assert rows[5][5] == "osaka.json"  # source_file もファイルごとに正しい


def test_group_rows_by_date():
    rows = [
        ("Tokyo", "2026-11-05T00:00"),  # 11/05 の始まり
        ("Tokyo", "2026-11-05T23:00"),  # 11/05 の最後（境界の直前）
        ("Tokyo", "2026-11-06T00:00"),  # 11/06 の始まり（境界の直後）
        ("Osaka", "2026-11-05T23:00"),  # 別の地点の 11/05
        ("Osaka", "2026-11-06T00:00"),  # 別の地点の 11/06
    ]
    by_date = bq.group_rows_by_date(rows)

    assert set(by_date.keys()) == {date(2026, 11, 5), date(2026, 11, 6)}
    assert len(by_date[date(2026, 11, 5)]) == 3
    assert ("Tokyo", "2026-11-05T23:00") in by_date[date(2026, 11, 5)]
    assert len(by_date[date(2026, 11, 6)]) == 2


def test_group_rows_by_date_empty():
    rows = []
    by_date = bq.group_rows_by_date(rows)

    assert by_date == {}
