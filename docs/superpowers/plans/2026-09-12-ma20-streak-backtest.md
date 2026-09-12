# Binance MA20 Streak Analysis and Backtest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and execute a cached Binance USDT perpetual MA20 streak event study plus a pullback-entry, ATR-trailing-stop Freqtrade baseline under `user_data`.

**Architecture:** A pandas-only core owns aggregation, point-in-time indicators, streak events, trade simulation, and statistics. A CLI layer owns Binance metadata, Freqtrade Feather files, exclusions, and CSV/JSON/Markdown output; a thin Freqtrade strategy imports the same core signal functions so analysis and trading cannot drift.

**Tech Stack:** Python 3.11+, pandas, numpy, Freqtrade/CCXT, unittest, Binance USD-M public API, Feather/pyarrow, Docker Freqtrade runtime.

---

### Task 1: Establish Pure Candle Aggregation and Indicators

**Files:**
- Create: `user_data/tests/test_ma20_streak_signal.py`
- Create: `user_data/scripts/ma20_streak_core.py`

- [ ] **Step 1: Write failing aggregation and indicator tests**

Add tests importing `aggregate_complete_candles`, `add_point_in_time_indicators`, and `timeframe_minutes`. Construct UTC 15-minute candles and assert that a complete 1h bucket has first open, maximum high, minimum low, last close, summed volume/quote volume, and its timestamp on the last 15-minute constituent. Assert incomplete/gapped buckets are omitted. Assert MA20 at row 19 equals the mean of closes 0..19 and does not change when a later close is mutated.

```python
def test_aggregate_1h_uses_only_four_complete_15m_candles(self):
    source = make_candles(8)
    result, quality = core.aggregate_complete_candles(source, "1h")
    self.assertEqual(list(result.index), [source.index[3], source.index[7]])
    self.assertEqual(result.iloc[0]["open"], source.iloc[0]["open"])
    self.assertEqual(result.iloc[0]["close"], source.iloc[3]["close"])
    self.assertEqual(quality["dropped_incomplete_buckets"], 0)
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python3 -m unittest user_data.tests.test_ma20_streak_signal.CandleAggregationTests -v`

Expected: import failure for missing `user_data.scripts.ma20_streak_core`.

- [ ] **Step 3: Implement minimal aggregation and point-in-time indicators**

Create these public functions with validation for UTC timestamps, duplicate timestamps, positive OHLC, and exact 15-minute continuity:

```python
TIMEFRAME_MINUTES = {"15m": 15, "1h": 60, "2h": 120, "4h": 240}

def timeframe_minutes(timeframe: str) -> int: ...
def normalize_ohlcv(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict]: ...
def aggregate_complete_candles(frame: pd.DataFrame, timeframe: str) -> tuple[pd.DataFrame, dict]: ...
def add_point_in_time_indicators(frame: pd.DataFrame, ma_period: int = 20, atr_period: int = 14) -> pd.DataFrame: ...
```

ATR uses true range against only the prior close and a simple rolling 14-period mean with `min_periods=14`.

- [ ] **Step 4: Run aggregation tests and verify GREEN**

Run: `python3 -m unittest user_data.tests.test_ma20_streak_signal.CandleAggregationTests -v`

Expected: all aggregation and indicator tests pass.

- [ ] **Step 5: Commit task files**

Run: `git add user_data/tests/test_ma20_streak_signal.py user_data/scripts/ma20_streak_core.py`

Run: `git commit -m "feat: add MA20 candle aggregation core"`

### Task 2: Implement Hold Windows, Streaks, and First-Reach Events

**Files:**
- Modify: `user_data/tests/test_ma20_streak_signal.py`
- Modify: `user_data/scripts/ma20_streak_core.py`

- [ ] **Step 1: Write failing signal tests**

Assert `close` and `low` modes differ, each hold compares against its own MA20, no rising-close condition exists, a run of ten true `holds` values produces streak `1,2,3,4,5` after the sixth through tenth bars, false resets to zero, and only exact threshold rows become events.

```python
def test_streak_counts_consecutive_matching_six_bar_windows(self):
    holds = pd.Series([True] * 10 + [False] + [True] * 6)
    streak = core.compute_window_streak(holds, hold_bars=6)
    self.assertEqual(streak.tolist(), [0, 0, 0, 0, 0, 1, 2, 3, 4, 5, 0, 0, 0, 0, 0, 0, 1])

def test_threshold_events_are_not_repeated(self):
    streak = pd.Series([0, 1, 2, 3, 4, 5, 6, 10, 11])
    events = core.first_reach_events(streak, [1, 2, 3, 5, 10])
    self.assertEqual(events["threshold"].tolist(), [1, 2, 3, 5, 10])
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python3 -m unittest user_data.tests.test_ma20_streak_signal.SignalTests -v`

Expected: missing signal function failures.

- [ ] **Step 3: Implement minimal signal functions**

```python
def compute_holds(frame: pd.DataFrame, mode: str = "close") -> pd.Series: ...
def compute_window_streak(holds: pd.Series, hold_bars: int = 6, contiguous: pd.Series | None = None) -> pd.Series: ...
def build_signal_frame(frame: pd.DataFrame, mode: str = "close", ma_period: int = 20, hold_bars: int = 6) -> pd.DataFrame: ...
def first_reach_events(streak: pd.Series, thresholds: Sequence[int]) -> pd.DataFrame: ...
```

Reject modes other than `close` and `low`; use no centered rolling windows, negative shifts, or backfills.

- [ ] **Step 4: Run signal tests and verify GREEN**

Run: `python3 -m unittest user_data.tests.test_ma20_streak_signal.SignalTests -v`

Expected: all signal tests pass.

- [ ] **Step 5: Commit signal behavior**

Run: `git add user_data/tests/test_ma20_streak_signal.py user_data/scripts/ma20_streak_core.py`

Run: `git commit -m "feat: add MA20 streak event detection"`

### Task 3: Implement Event Returns and Grouped Statistics

**Files:**
- Modify: `user_data/tests/test_ma20_streak_signal.py`
- Modify: `user_data/scripts/ma20_streak_core.py`

- [ ] **Step 1: Write failing event-study tests**

For a deterministic frame, assert signal row `i` enters at row `i+1` open, horizon 2 exits at row `i+2` close, MFE uses highs from rows `i+1..i+2`, and MAE uses lows from those rows. Assert insufficient future bars omit that horizon. Test trailing 24h quote volume uses 96 completed 15-minute candles through the signal and fixed buckets.

```python
def test_event_metrics_start_at_next_open(self):
    row = core.measure_event_horizon(frame, signal_position=20, horizon=2)
    self.assertEqual(row["entry_price"], frame.iloc[21]["open"])
    self.assertEqual(row["exit_price"], frame.iloc[22]["close"])
    self.assertEqual(row["mfe"], frame.iloc[21:23]["high"].max() / row["entry_price"] - 1)
```

- [ ] **Step 2: Run event tests and verify RED**

Run: `python3 -m unittest user_data.tests.test_ma20_streak_signal.EventStudyTests -v`

Expected: missing event/statistics function failures.

- [ ] **Step 3: Implement event rows and statistics**

```python
VOLUME_BUCKETS = ((10_000_000, "<10m"), (50_000_000, "10m-50m"), (200_000_000, "50m-200m"))
def trailing_quote_volume(base_15m: pd.DataFrame) -> pd.Series: ...
def volume_bucket(value: float, boundaries=VOLUME_BUCKETS) -> str: ...
def measure_event_horizon(frame: pd.DataFrame, signal_position: int, horizon: int) -> dict | None: ...
def build_event_table(..., horizons=(1, 2, 4, 8, 16)) -> pd.DataFrame: ...
def summarize_events(events: pd.DataFrame, group_columns: Sequence[str]) -> pd.DataFrame: ...
def maximum_compounded_drawdown(returns: pd.Series) -> float: ...
```

`payoff_ratio` is mean positive return divided by absolute mean negative return. Groups with no wins or no losses return JSON-safe null for the ratio.

- [ ] **Step 4: Run event tests and verify GREEN**

Run: `python3 -m unittest user_data.tests.test_ma20_streak_signal.EventStudyTests -v`

Expected: all event/statistics tests pass.

- [ ] **Step 5: Commit event study**

Run: `git add user_data/tests/test_ma20_streak_signal.py user_data/scripts/ma20_streak_core.py`

Run: `git commit -m "feat: add MA20 event return statistics"`

### Task 4: Implement Pullback Fill and Monotonic ATR Stop Models

**Files:**
- Modify: `user_data/tests/test_ma20_streak_signal.py`
- Modify: `user_data/scripts/ma20_streak_core.py`

- [ ] **Step 1: Write failing execution-model tests**

Assert `entry_limit = ma20 + ratio * (close - ma20)`, extension above `2*ATR` is rejected, a next open below signal MA cancels, a next open below the limit but above MA fills at open, an open above limit fills only after a low touch, and no touch expires. Assert ATR stop distance is clamped to 2%-8% at entry and `max(previous_stop, candidate_stop)` never loosens.

```python
def test_pullback_limit_is_halfway_to_ma20(self):
    self.assertEqual(core.pullback_entry_limit(104, 100, 0.5), 102)

def test_trailing_stop_never_moves_down(self):
    stop = core.next_atr_trailing_stop(100, 108, 3, 2.5, previous_stop=102, min_risk=0.02, max_risk=0.08)
    self.assertEqual(stop, 102)
```

- [ ] **Step 2: Run execution tests and verify RED**

Run: `python3 -m unittest user_data.tests.test_ma20_streak_signal.ExecutionModelTests -v`

Expected: missing execution-model function failures.

- [ ] **Step 3: Implement execution helpers**

```python
def is_overextended(close: float, ma20: float, atr14: float, max_atr: float = 2.0) -> bool: ...
def pullback_entry_limit(close: float, ma20: float, ratio: float = 0.5) -> float: ...
def simulate_pullback_fill(next_candles: pd.DataFrame, limit: float, signal_ma20: float) -> dict: ...
def initial_atr_stop(entry: float, atr: float, multiple: float = 2.5, min_risk: float = 0.02, max_risk: float = 0.08) -> float: ...
def next_atr_trailing_stop(entry: float, highest: float, atr: float, multiple: float, previous_stop: float, min_risk: float, max_risk: float) -> float: ...
```

- [ ] **Step 4: Run execution tests and verify GREEN**

Run: `python3 -m unittest user_data.tests.test_ma20_streak_signal.ExecutionModelTests -v`

Expected: all execution tests pass.

- [ ] **Step 5: Commit execution rules**

Run: `git add user_data/tests/test_ma20_streak_signal.py user_data/scripts/ma20_streak_core.py`

Run: `git commit -m "feat: add pullback entry and ATR trailing stop"`

### Task 5: Build Market Metadata, Exclusions, and Reports

**Files:**
- Create: `user_data/scripts/analyze_ma20_streak.py`
- Modify: `user_data/tests/test_ma20_streak_signal.py`

- [ ] **Step 1: Write failing CLI-layer tests**

Load the CLI module without network calls and assert market filtering preserves both accepted contract types, current symbols missing from CCXT receive `unsupported_by_ccxt`, missing Feather files receive `missing_15m_data`, insufficient rows receive `insufficient_history`, and report writing creates CSV, JSON, and Markdown containing the survivorship-bias warning.

```python
def test_market_filter_keeps_tradifi_perpetual(self):
    included, excluded = analysis.classify_exchange_symbols(exchange_info_fixture, ccxt_ids={"BTCUSDT", "XAUUSDT"})
    self.assertEqual({row["contractType"] for row in included}, {"PERPETUAL", "TRADIFI_PERPETUAL"})
```

- [ ] **Step 2: Run CLI tests and verify RED**

Run: `python3 -m unittest user_data.tests.test_ma20_streak_signal.AnalysisCliTests -v`

Expected: missing `analyze_ma20_streak` functions.

- [ ] **Step 3: Implement the analysis CLI**

Provide these commands and functions:

```python
def fetch_exchange_info(cache_path: Path, refresh: bool = False) -> dict: ...
def classify_exchange_symbols(payload: dict, ccxt_ids: set[str]) -> tuple[list[dict], list[dict]]: ...
def load_futures_feather(data_dir: Path, symbol: str) -> pd.DataFrame: ...
def analyze_symbol(symbol_meta: dict, base_15m: pd.DataFrame, modes, timeframes, thresholds, horizons) -> tuple[pd.DataFrame, dict]: ...
def write_outputs(result: dict, output_dir: Path) -> dict[str, Path]: ...
```

CLI subcommands are `snapshot`, `analyze`, and `verify-cache`; options include `--symbols`, `--all-symbols`, `--modes`, `--timeframes`, `--timerange`, `--refresh-market`, and `--output-dir`. `snapshot` writes current market metadata even when CCXT rejects TradFi.

- [ ] **Step 4: Run CLI tests and verify GREEN**

Run: `python3 -m unittest user_data.tests.test_ma20_streak_signal.AnalysisCliTests -v`

Expected: all CLI/report tests pass.

- [ ] **Step 5: Commit CLI and reports**

Run: `git add user_data/tests/test_ma20_streak_signal.py user_data/scripts/analyze_ma20_streak.py`

Run: `git commit -m "feat: add MA20 market analysis reports"`

### Task 6: Build the Thin Freqtrade Strategy and Configuration

**Files:**
- Create: `user_data/strategies/ma20_streak_signal.py`
- Create: `user_data/config-ma20-streak-backtest.json`
- Modify: `user_data/tests/test_ma20_streak_signal.py`

- [ ] **Step 1: Write failing strategy tests**

Instantiate `Ma20StreakSignalStrategy`, set `ma20_streak` config, and assert only the final 15-minute constituent of an eligible target candle has `enter_long=1`; overextended and non-threshold rows do not enter; `custom_entry_price` returns the precomputed limit; `confirm_trade_entry` rejects rates below signal MA; `custom_exit` returns `max_hold_N_bars`; and custom stoploss uses a stop that cannot loosen.

```python
def test_strategy_marks_signal_only_at_completed_target_boundary(self):
    prepared = strategy.populate_indicators(make_signal_frame(), {"pair": "BTC/USDT:USDT"})
    entered = strategy.populate_entry_trend(prepared, {"pair": "BTC/USDT:USDT"})
    self.assertEqual(entered.index[entered["enter_long"] == 1].tolist(), [prepared.index[-1]])
```

- [ ] **Step 2: Run strategy tests and verify RED**

Run: `python3 -m unittest user_data.tests.test_ma20_streak_signal.StrategyTests -v`

Expected: missing strategy module/class.

- [ ] **Step 3: Implement strategy callbacks**

Create `Ma20StreakSignalStrategy(IStrategy)` with `timeframe="15m"`, `can_short=False`, `startup_candle_count=640`, `minimal_roi={}`, `stoploss=-0.08`, and `use_custom_stoploss=True`. Read explicit settings from `self.config["ma20_streak"]`; default to close/15m/x1/50% pullback/2 ATR extension/2.5 ATR trail/2%-8% risk/1 held target bar. Implement `populate_indicators`, `populate_entry_trend`, `populate_exit_trend`, `custom_entry_price`, `confirm_trade_entry`, `check_entry_timeout`, `custom_stoploss`, and `custom_exit` using core helpers.

- [ ] **Step 4: Add valid futures config**

Use Binance futures isolated mode, 15m base timeframe, 7 smoke pairs, static pairlist, limit entry, market stoploss, disabled API/Telegram, explicit 0.05% fee, 1000 USDT dry-run wallet, and a `ma20_streak` settings object. Do not put secrets in the file.

- [ ] **Step 5: Run strategy and config tests and verify GREEN**

Run: `python3 -m unittest user_data.tests.test_ma20_streak_signal.StrategyTests -v`

Expected: all strategy tests pass.

- [ ] **Step 6: Commit strategy and config**

Run: `git add user_data/tests/test_ma20_streak_signal.py user_data/strategies/ma20_streak_signal.py user_data/config-ma20-streak-backtest.json`

Run: `git commit -m "feat: add MA20 streak Freqtrade strategy"`

### Task 7: Download Cached Smoke Data and Run Event Study

**Files:**
- Create/extend cache: `user_data/data/binance/futures/*-15m-futures.feather`
- Create: `user_data/backtest_results/ma20-streak/smoke/*`

- [ ] **Step 1: Verify runtime and Binance/CCXT market mappings**

Run Docker Freqtrade `list-markets` for futures and save the result through the analysis `snapshot` command. Verify Binance IDs `XAUUSDT` and `TSLAUSDT` are `TRADIFI_PERPETUAL`; record whether CCXT/Freqtrade exposes `XAU/USDT:USDT` and `TSLA/USDT:USDT`.

- [ ] **Step 2: Download or extend 12-month smoke cache**

Run:

```bash
docker compose run --rm freqtrade download-data \
  --config /freqtrade/user_data/config-ma20-streak-backtest.json \
  --pairs BTC/USDT:USDT ETH/USDT:USDT DOGE/USDT:USDT WIF/USDT:USDT PENGU/USDT:USDT XAU/USDT:USDT TSLA/USDT:USDT \
  --timeframes 15m \
  --timerange 20250912-20260912 \
  --trading-mode futures
```

Do not erase existing data. Unsupported pairs remain in exclusions with command output summarized.

- [ ] **Step 3: Verify cache coverage and gaps**

Run: `python3 user_data/scripts/analyze_ma20_streak.py verify-cache --symbols BTCUSDT,ETHUSDT,DOGEUSDT,WIFUSDT,PENGUUSDT,XAUUSDT,TSLAUSDT --timerange 20250912-20260912`

Expected: one row per requested symbol with start, end, candle count, missing intervals, and inclusion/exclusion status.

- [ ] **Step 4: Run both-mode smoke event study**

Run: `python3 user_data/scripts/analyze_ma20_streak.py analyze --symbols BTCUSDT,ETHUSDT,DOGEUSDT,WIFUSDT,PENGUUSDT,XAUUSDT,TSLAUSDT --modes close,low --timeframes 15m,1h,2h,4h --timerange 20250912-20260912 --output-dir user_data/backtest_results/ma20-streak/smoke`

Expected: nonempty event/group CSVs for available symbols, JSON metadata/exclusions, and Markdown with survivorship warning.

### Task 8: Run Smoke Backtests and Lookahead Analysis

**Files:**
- Create: `user_data/scripts/run_ma20_streak_backtests.py`
- Modify: `user_data/tests/test_ma20_streak_signal.py`
- Create: `user_data/backtest_results/ma20-streak/backtests/*`
- Create: `user_data/backtest_results/ma20-streak/lookahead/*`

- [ ] **Step 1: Write failing matrix-runner tests**

Assert `matrix_cases` returns the requested Cartesian product, `write_case_config` changes only the copied `ma20_streak` settings and output-safe case name, `parse_backtest_zip` extracts trade count/return/profit factor/drawdown, and `stability_score` rejects fewer than 30 trades while preferring lower dispersion and drawdown over a single extreme return.

```python
def test_matrix_cases_are_complete_and_named(self):
    cases = runner.matrix_cases(["15m", "1h"], [1, 3], [1, 4])
    self.assertEqual(len(cases), 8)
    self.assertEqual(cases[0]["name"], "close-15m-x1-h1")

def test_stability_score_requires_sample_size(self):
    self.assertIsNone(runner.stability_score({"trade_count": 29, "median_return": 0.1}))
```

- [ ] **Step 2: Run matrix-runner tests and verify RED**

Run: `python3 -m unittest user_data.tests.test_ma20_streak_signal.BacktestRunnerTests -v`

Expected: missing runner module/functions.

- [ ] **Step 3: Implement the matrix runner**

Implement `matrix_cases`, `write_case_config`, `run_case`, `parse_backtest_zip`, `stability_score`, and `write_matrix_summary`. The CLI accepts repeated/comma-separated timeframes, thresholds, and holds plus `--dry-run` to print exact Docker commands without running them. Every case gets its own copied config and export filename under the requested output directory.

- [ ] **Step 4: Run matrix-runner tests and verify GREEN**

Run: `python3 -m unittest user_data.tests.test_ma20_streak_signal.BacktestRunnerTests -v`

Expected: all matrix-runner tests pass.

- [ ] **Step 5: Run focused backtest matrix**

Use close mode with timeframes `15m,1h,2h,4h`, thresholds `1,2,3,5,10`, and holds `1,2,4,8,16`. Start with x1/x3 and hold 1/4 on all timeframes; then run remaining combinations when smoke data and trade counts permit. Each invocation overrides only `ma20_streak` values using generated configs under the result directory and exports trades.

- [ ] **Step 6: Parse matrix results and rank stability**

Add matrix results to the Markdown/JSON report. Stability score requires at least 30 trades and rewards positive median return, positive profit factor margin, lower drawdown, and similar performance across timeframes/holds. Keep raw top-return ranking separate from stable ranking.

- [ ] **Step 7: Run lookahead-analysis**

Run the best sufficiently populated smoke configuration with:

```bash
docker compose run --rm freqtrade lookahead-analysis \
  --config /freqtrade/user_data/config-ma20-streak-backtest.json \
  --strategy-path /freqtrade/user_data/strategies \
  --strategy Ma20StreakSignalStrategy \
  --timerange 20250912-20260912 \
  --minimum-trade-amount 5 \
  --targeted-trade-amount 20 \
  --lookahead-analysis-exportfilename /freqtrade/user_data/backtest_results/ma20-streak/lookahead/smoke.csv
```

Expected: `has_bias` is `No` for indicators and entry/exit signals. If trade count is too low, lower only the analysis minimum or use the most populated valid x1 configuration; do not alter signal semantics.

### Task 9: Expand the Universe and Produce Final Evidence

**Files:**
- Extend cache: `user_data/data/binance/futures/*`
- Create: `user_data/backtest_results/ma20-streak/full/*`
- Modify: `user_data/backtest_results/ma20-streak/full/summary.md`

- [ ] **Step 1: Enumerate the current full universe**

Use the cached Binance market snapshot and CCXT/Freqtrade mapping to create included and excluded pair files. Keep PERPETUAL and TRADIFI counts separate.

- [ ] **Step 2: Download all retrievable 15m histories incrementally**

Invoke Freqtrade `download-data` in bounded pair batches, preserving existing Feather cache. Continue past per-pair errors and merge every error into exclusions.

- [ ] **Step 3: Run full event analysis**

Run both modes and all four timeframes over available 12-month histories. Produce full event/group CSV, JSON, Markdown, data-quality, and exclusions artifacts.

- [ ] **Step 4: Backtest stable candidates**

Run full-universe Freqtrade backtests for the smoke matrix's stable candidates rather than all 100 combinations. Run lookahead-analysis again on the final selected configuration.

- [ ] **Step 5: Run final verification**

Run:

```bash
python3 -m unittest user_data.tests.test_ma20_streak_signal -v
git diff --check
```

Inspect result artifacts for included/excluded counts, data coverage, group completeness, fee/slippage/funding disclosure, backtest trade counts, and `has_bias=No` evidence.

- [ ] **Step 6: Commit final report tooling updates**

Stage only MA20 files and commit with `feat: complete MA20 streak backtest workflow`. Do not stage or revert unrelated working-tree changes.
