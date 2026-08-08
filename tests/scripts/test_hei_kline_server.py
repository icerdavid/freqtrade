from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Iterator
from urllib.error import HTTPError
from urllib.request import urlopen

import pandas as pd
import pytest

from scripts.hei_kline_viewer.data import CandleStore
from scripts.hei_kline_viewer.server import create_server


@pytest.fixture
def running_server(tmp_path: Path) -> Iterator[str]:
    timestamps = [index * 60 for index in range(8)]
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(timestamps, unit="s", utc=True),
            "open": [float(index + 1) for index in range(8)],
            "high": [float(index + 1.5) for index in range(8)],
            "low": [float(index + 0.5) for index in range(8)],
            "close": [float(index + 1.25) for index in range(8)],
            "volume": [float((index + 1) * 100) for index in range(8)],
        }
    )
    frame.to_feather(tmp_path / "hei-15m.feather")
    frame.to_feather(tmp_path / "xrp-15m.feather")
    store = CandleStore(tmp_path, {"15m": "hei-15m.feather"}, max_limit=5)
    xrp_store = CandleStore(tmp_path, {"15m": "xrp-15m.feather"}, max_limit=5)
    server = create_server(
        "127.0.0.1",
        0,
        store,
        stores={"HEI": store, "XRP": xrp_store},
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_root_returns_chart_page(running_server: str) -> None:
    with urlopen(f"{running_server}/") as response:
        body = response.read()

        assert response.status == 200
        assert response.headers["Content-Type"].startswith("text/html")
        assert response.headers["Cache-Control"] == "no-store"
        assert b"LightweightCharts" in body


def test_candle_endpoint_returns_json_chunk(running_server: str) -> None:
    with urlopen(f"{running_server}/api/candles?timeframe=15m&limit=2") as response:
        payload = json.load(response)

        assert response.headers["Content-Type"] == "application/json; charset=utf-8"
        assert [candle["time"] for candle in payload["candles"]] == [360, 420]
        assert payload["has_more"] is True


def test_candle_endpoint_supports_exclusive_before(running_server: str) -> None:
    with urlopen(
        f"{running_server}/api/candles?timeframe=15m&before=180&limit=3"
    ) as response:
        payload = json.load(response)

        assert [candle["time"] for candle in payload["candles"]] == [0, 60, 120]
        assert payload["has_more"] is False


def test_candle_endpoint_selects_xrp_store_and_returns_derived_fields(
    running_server: str,
) -> None:
    with urlopen(
        f"{running_server}/api/candles?symbol=XRP&timeframe=15m&limit=1"
    ) as response:
        payload = json.load(response)

        assert payload["symbol"] == "XRP"
        assert payload["candles"][0]["time"] == 420
        assert payload["candles"][0]["range"] == 1.0
        assert payload["candles"][0]["bb_middle"] is None


@pytest.mark.parametrize(
    "query, message",
    [
        ("symbol=NOPE&timeframe=15m&limit=2", "Unsupported symbol"),
        ("timeframe=../secret&limit=2", "Unsupported timeframe"),
        ("timeframe=15m&limit=invalid", "limit must be an integer"),
        ("timeframe=15m&before=invalid", "before must be an integer"),
        ("limit=2", "Missing query parameter: timeframe"),
        ("timeframe=15m&timeframe=1m", "timeframe must appear once"),
    ],
)
def test_bad_query_returns_400_json(
    running_server: str, query: str, message: str
) -> None:
    with pytest.raises(HTTPError) as error:
        urlopen(f"{running_server}/api/candles?{query}")

    assert error.value.code == 400
    assert message in json.load(error.value)["error"]


def test_unknown_route_returns_404(running_server: str) -> None:
    with pytest.raises(HTTPError) as error:
        urlopen(f"{running_server}/missing")

    assert error.value.code == 404
    assert json.load(error.value) == {"error": "Not found"}
