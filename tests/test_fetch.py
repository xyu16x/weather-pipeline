import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import requests

from pipeline import fetch

FIXTURE = Path(__file__).parent / "fixtures" / "sample_response.json"
D = date(2026, 10, 1)


def _resp(status, body=None):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = body or {}
    r.text = "err"
    return r


def test_success_first_try():
    sess = MagicMock()
    sess.get.return_value = _resp(200, {"ok": 1})
    assert fetch.fetch_hourly(35, 139, D, D, session=sess) == {"ok": 1}
    assert sess.get.call_count == 1


def test_retry_on_5xx_then_success():
    sess = MagicMock()
    sess.get.side_effect = [_resp(503), _resp(429), _resp(200, {"ok": 1})]
    out = fetch.fetch_hourly(35, 139, D, D, session=sess, backoff_sec=0)
    assert out == {"ok": 1}
    assert sess.get.call_count == 3


def test_retry_on_network_error_then_give_up():
    sess = MagicMock()
    sess.get.side_effect = requests.ConnectionError("boom")
    with pytest.raises(fetch.FetchError):
        fetch.fetch_hourly(35, 139, D, D, session=sess, max_retries=2, backoff_sec=0)
    assert sess.get.call_count == 3


def test_4xx_fails_immediately():
    sess = MagicMock()
    sess.get.return_value = _resp(400)
    with pytest.raises(fetch.FetchError):
        fetch.fetch_hourly(35, 139, D, D, session=sess, backoff_sec=0)
    assert sess.get.call_count == 1


def test_invalid_range():
    with pytest.raises(ValueError):
        fetch.fetch_hourly(35, 139, date(2026, 10, 2), D)


def test_save_raw_is_idempotent(tmp_path):
    payload = json.loads(FIXTURE.read_text())
    p1 = fetch.save_raw(payload, "Tokyo", D, D, tmp_path)
    p2 = fetch.save_raw(payload, "Tokyo", D, D, tmp_path)
    assert p1 == p2
    assert len(list(tmp_path.glob("*.json"))) == 1
