from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from scripts.hei_kline_viewer.data import CandleStore, QueryError


def write_test_feather(
    directory: Path,
    *,
    rows: int = 8,
    reversed_order: bool = False,
    duplicate_last: bool = False,
) -> None:
    timestamps = [index * 60 for index in range(rows)]
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(timestamps, unit="s", utc=True),
            "open": [float(index + 1) for index in range(rows)],
            "high": [float(index + 1.5) for index in range(rows)],
            "low": [float(index + 0.5) for index in range(rows)],
            "close": [float(index + 1.25) for index in range(rows)],
            "volume": [float((index + 1) * 100) for index in range(rows)],
        }
    )
    if duplicate_last:
        frame = pd.concat([frame, frame.tail(1)], ignore_index=True)
    if reversed_order:
        frame = frame.iloc[::-1].reset_index(drop=True)
    frame.to_feather(directory / "hei-15m.feather")


def test_latest_chunk_is_sorted_unique_and_reports_more(tmp_path: Path) -> None:
    write_test_feather(tmp_path, rows=8, reversed_order=True, duplicate_last=True)
    store = CandleStore(tmp_path, {"15m": "hei-15m.feather"}, max_limit=5)

    result = store.query("15m", limit=3)

    assert [item["time"] for item in result["candles"]] == [300, 360, 420]
    assert result["has_more"] is True
    assert result["timeframe"] == "15m"


def test_before_is_exclusive_and_oldest_chunk_has_no_more(tmp_path: Path) -> None:
    write_test_feather(tmp_path, rows=8)
    store = CandleStore(tmp_path, {"15m": "hei-15m.feather"}, max_limit=5)

    result = store.query("15m", before=180, limit=3)

    assert [item["time"] for item in result["candles"]] == [0, 60, 120]
    assert result["has_more"] is False


def test_candle_values_are_plain_python_numbers(tmp_path: Path) -> None:
    write_test_feather(tmp_path, rows=2)
    store = CandleStore(tmp_path, {"15m": "hei-15m.feather"})

    candle = store.query("15m", limit=1)["candles"][0]

    assert type(candle["time"]) is int
    for field in ("open", "high", "low", "close", "volume"):
        assert type(candle[field]) is float


@pytest.mark.parametrize("timeframe", ["5m", "../secret", "1m/../../x"])
def test_unknown_timeframe_is_rejected(tmp_path: Path, timeframe: str) -> None:
    store = CandleStore(tmp_path, {"15m": "hei-15m.feather"})

    with pytest.raises(QueryError, match="Unsupported timeframe"):
        store.query(timeframe)


@pytest.mark.parametrize("limit", [0, -1, 5001])
def test_limit_outside_bounds_is_rejected(tmp_path: Path, limit: int) -> None:
    store = CandleStore(tmp_path, {"15m": "hei-15m.feather"}, max_limit=5000)

    with pytest.raises(QueryError, match="limit"):
        store.query("15m", limit=limit)


def test_missing_feather_file_has_clear_error(tmp_path: Path) -> None:
    store = CandleStore(tmp_path, {"15m": "missing.feather"})

    with pytest.raises(QueryError, match="Candle file not found"):
        store.query("15m")
