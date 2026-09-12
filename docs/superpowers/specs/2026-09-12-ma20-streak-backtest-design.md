# Binance USDT Perpetual MA20 Streak Analysis and Backtest Design

## Objective

Implement a reproducible MA20 streak event study and a baseline Freqtrade strategy under `user_data` without modifying Freqtrade core or the PathToFreedom project. The scanner behavior in `/Volumes/Work/1_projects/PathToFreedom/binance_scanner_server.py` and its `binance-ma20-perp-scanner` skill is the sole source of truth for signal semantics.

The implementation analyzes both `close` and `low` modes. The default mode for reports and strategy runs is `close`.

## Market Universe and Data

The universe comes from the current Binance USD-M Futures `exchangeInfo` response. Candidates must have:

- `quoteAsset == USDT`
- `status == TRADING`
- `contractType` equal to `PERPETUAL` or `TRADIFI_PERPETUAL`

The pipeline stores a dated market metadata snapshot. Every symbol that is discovered but not analyzed is written to an exclusion report with a machine-readable reason, including unsupported CCXT/Freqtrade mapping, missing OHLCV, incomplete history, download failure, malformed candles, and unsupported contract type. `TRADIFI_PERPETUAL` is never silently treated as invalid.

The initial smoke universe is:

- `BTCUSDT`
- `ETHUSDT`
- `DOGEUSDT`
- `WIFUSDT`
- `PENGUUSDT`
- `XAUUSDT`
- `TSLAUSDT`

The first production data target is the most recent 12 months of 15-minute OHLCV. Existing Feather files under `user_data/data/binance/futures` are reused. Downloads extend rather than replace cached history. Mark-price and funding-rate data are downloaded when Freqtrade and CCXT expose them.

The full run expands from the smoke universe to every currently retrievable candidate. Reports explicitly state that using the current contract universe creates survivorship bias because delisted contracts are absent unless a separate historical-universe source is available.

## Candle Aggregation

The canonical input is 15-minute OHLCV with UTC open timestamps. Duplicate timestamps are rejected or deterministically deduplicated and reported. Gaps are detected per symbol.

Target timeframes are `15m`, `1h`, `2h`, and `4h`. Higher timeframes are aggregated on UTC Binance boundaries from complete 15-minute candles only. A bucket is emitted only when it contains exactly 4, 8, or 16 consecutive 15-minute candles as appropriate. Partial first, last, or gapped buckets are excluded and counted in data-quality output.

For each target candle, MA20 uses that candle's close and the preceding 19 closes. ATR14 uses only target candles available through that candle's close. No backward fill or future-derived grouping is permitted.

## Signal and Streak Rules

For each target candle, `holds` is:

- `close >= MA20` in `close` mode.
- `low >= MA20` in `low` mode.

A six-bar window matches when all six candles hold against their own point-in-time MA20. It does not require net appreciation or monotonic closes.

`streak` is the number of consecutive matching six-bar rolling windows ending at the current target candle. It resets to zero when a window fails or when target candles are not contiguous.

Threshold events are emitted only when streak first reaches `1`, `2`, `3`, `5`, or `10`. Since streak advances one window at a time, this is equivalent to `streak == threshold`. Later candles above the same threshold do not create duplicate events.

## Event Study

The raw event study intentionally measures the unfiltered scanner signal. An event is confirmed after its target candle closes. Entry is the next target candle's open. Horizons are 1, 2, 4, 8, and 16 target candles, with return measured from entry open to the close of the Nth held candle.

For every event and horizon, the pipeline calculates:

- raw return and optional fee-adjusted return
- MFE from entry to the maximum high in the holding window
- MAE from entry to the minimum low in the holding window
- entry, exit, and horizon timestamps

Grouped summaries include sample count, win rate, mean return, median return, average winning return divided by absolute average losing return, mean/median MFE and MAE, and maximum drawdown. Event-study drawdown uses an equal-weight compounded event-return sequence ordered by exit time. Reports warn that overlapping events make this diagnostic different from a realizable portfolio drawdown.

Groups include mode, timeframe, streak threshold, fixed trailing-24-hour USDT quote-volume bucket, contract type, and horizon. Trailing volume is computed only from completed 15-minute candles available at the event time. Default buckets are `<10m`, `10m-50m`, `50m-200m`, and `>=200m` USDT and are configurable.

Outputs under `user_data/backtest_results/ma20-streak/` include event-level CSV, grouped CSV, exclusions CSV, market snapshot JSON, complete analysis JSON, and a readable Markdown summary.

## Baseline Strategy Entry

The strategy is long-only and allows at most one open trade per pair. A setup becomes eligible when the selected timeframe streak first equals configurable `min_streak`. The default signal mode is `close`.

An eligible setup is rejected when the signal close is more than `2.0 * ATR14` above MA20. This extension limit is configurable.

For an accepted setup, the buy limit is halfway between MA20 and the signal close:

```text
entry_limit = MA20 + entry_pullback_ratio * (signal_close - MA20)
entry_pullback_ratio = 0.5 by default
```

The limit order becomes active after signal-candle close and remains valid only for the next target-timeframe candle. If the next target candle opens between MA20 and the limit, execution uses the better opening price. If it opens above the limit, the order fills only if subsequent 15-minute data touches the limit. If the next target candle opens below the signal-time MA20, the setup is canceled. An unfilled order is canceled at the end of the validity window and is not chased.

Fills inside a 15-minute candle use conservative OHLC assumptions and are labeled as simulated limit fills. Entry slippage is applied only when the modeled execution is marketable at the open; passive limit fills do not receive favorable price improvement.

## Baseline Strategy Exit

There is no fixed profit target. Every trade has a volatility-adjusted trailing stop:

```text
initial_stop = entry_price - 2.5 * ATR14_at_entry
candidate_stop = highest_completed_price_since_entry - 2.5 * current_ATR14
active_stop = max(previous_active_stop, candidate_stop)
```

The stop never moves downward. Configurable percentage bounds keep initial stop distance between 2% and 8%. Stop evaluation uses only completed 15-minute data and Freqtrade's conservative stop execution rules.

Each matrix run also has a maximum holding period of 1, 2, 4, 8, or 16 selected target-timeframe candles. A trade exits on the first of:

1. trailing stop execution;
2. maximum holding period expiry;
3. forced end-of-backtest closure.

The time exit is signaled after the final constituent 15-minute candle and executes according to Freqtrade's next-open model. Fees use exchange/config values. A fixed adverse slippage model is configurable and reported. Funding is included only when Freqtrade can retrieve the required funding and mark-price series; otherwise reports state that it is absent.

## Freqtrade Integration

Production logic is split into:

- `user_data/scripts/ma20_streak_core.py`: pure candle, signal, event, fill, stop, and statistics functions.
- `user_data/scripts/analyze_ma20_streak.py`: CLI orchestration, market snapshots, data loading, reports, and exclusion handling.
- `user_data/strategies/ma20_streak_signal.py`: thin Freqtrade adapter that reuses the same signal calculations.
- `user_data/config-ma20-streak-backtest.json`: futures backtest defaults.
- `user_data/tests/test_ma20_streak_signal.py`: focused unit and strategy tests.

Strategy settings for mode, timeframe, minimum streak, pullback ratio, extension limit, ATR multiplier, stop bounds, and holding bars are explicit and reproducible. The analysis script records all effective settings in JSON and Markdown outputs.

## Test-Driven Implementation

Implementation follows red-green-refactor. Failing tests are written and run before production functions for:

- complete and incomplete timeframe aggregation
- point-in-time MA20 and ATR14
- close/low hold differences
- six-window streak progression and reset
- exact first-threshold events
- next-open event returns, MFE, and MAE
- trailing-volume grouping without future data
- exclusion records and contract-type preservation
- pullback price, setup cancellation, and expiry
- overextension rejection
- monotonic ATR trailing stops
- higher-timeframe signal placement on the last constituent 15-minute candle

After unit tests pass, verification runs in this order:

1. smoke-universe data coverage and event analysis;
2. smoke strategy backtests across selected streak and hold combinations;
3. smoke `lookahead-analysis` with enough trades for validation;
4. full retrievable-universe data extension and analysis;
5. selected stable-combination full-universe backtests and lookahead checks.

Stability is ranked using consistency across timeframes, streaks, hold periods, sample sufficiency, drawdown, and dispersion rather than maximum return alone.

## Deliverables

The final handoff reports included and excluded counts, exclusion reasons, data ranges and gaps, grouped event results, stable combinations, exact commands, fee/slippage/funding treatment, unit-test results, backtest results, lookahead results, and every new or modified file.
