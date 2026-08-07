from __future__ import annotations

from pathlib import Path
from typing import Mapping

import pandas as pd


TIMEFRAME_FILES = {
    "1m": "HEI_USDT_USDT-1m-futures.feather",
    "15m": "HEI_USDT_USDT-15m-futures.feather",
    "1h": "HEI_USDT_USDT-1h-futures.feather",
    "2h": "HEI_USDT_USDT-2h-futures.feather",
    "4h": "HEI_USDT_USDT-4h-futures.feather",
    "1d": "HEI_USDT_USDT-1d-futures.feather",
}

REQUIRED_COLUMNS = ("date", "open", "high", "low", "close", "volume")
NUMERIC_COLUMNS = ("open", "high", "low", "close", "volume")


class QueryError(ValueError):
    """A candle request cannot be fulfilled safely."""


class CandleStore:
    """Load allowlisted Feather files and return ascending candle chunks."""

    def __init__(
        self,
        data_dir: Path,
        files: Mapping[str, str] = TIMEFRAME_FILES,
        max_limit: int = 5000,
    ) -> None:
        self.data_dir = Path(data_dir)
        self.files = dict(files)
        self.max_limit = max_limit
        self._frames: dict[str, pd.DataFrame] = {}

    def query(
        self,
        timeframe: str,
        *,
        before: int | None = None,
        limit: int = 1500,
    ) -> dict[str, object]:
        if timeframe not in self.files:
            raise QueryError(f"Unsupported timeframe: {timeframe}")
        if not 1 <= limit <= self.max_limit:
            raise QueryError(f"limit must be between 1 and {self.max_limit}")

        frame = self._load(timeframe)
        eligible = frame if before is None else frame[frame["time"] < before]
        chunk = eligible.tail(limit)
        candles = chunk[["time", *NUMERIC_COLUMNS]].to_dict("records")

        return {
            "timeframe": timeframe,
            "candles": candles,
            "has_more": len(eligible) > len(chunk),
        }

    def _load(self, timeframe: str) -> pd.DataFrame:
        cached = self._frames.get(timeframe)
        if cached is not None:
            return cached

        path = self.data_dir / self.files[timeframe]
        if not path.is_file():
            raise QueryError(f"Candle file not found: {path}")

        try:
            source = pd.read_feather(path)
        except Exception as exc:
            raise QueryError(f"Unable to read candle file: {path}") from exc

        missing = [column for column in REQUIRED_COLUMNS if column not in source.columns]
        if missing:
            raise QueryError(f"Candle file is missing columns: {', '.join(missing)}")

        frame = source.loc[:, REQUIRED_COLUMNS].copy()
        try:
            dates = pd.to_datetime(frame.pop("date"), utc=True, errors="raise")
            frame.insert(0, "time", dates.dt.as_unit("s").astype("int64"))
            for column in NUMERIC_COLUMNS:
                frame[column] = pd.to_numeric(frame[column], errors="raise").astype(float)
        except (TypeError, ValueError) as exc:
            raise QueryError(f"Candle file contains invalid values: {path}") from exc

        frame = (
            frame.drop_duplicates(subset="time", keep="last")
            .sort_values("time", kind="stable")
            .reset_index(drop=True)
        )
        self._frames[timeframe] = frame
        return frame
