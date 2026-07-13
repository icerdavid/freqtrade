# BTC/ETH 15m Trend Pullback Strategy Design

Date: 2026-07-13

## Purpose

Build a new Freqtrade futures strategy for a small 50 USDT account that avoids meme coins, trades only high-liquidity BTC/ETH perpetuals, and prioritizes drawdown control over headline backtest profit.

This replaces the previous BeatSpike and PlayBollinger experiments as the active strategy direction. The old strategies and stale backtest artifacts will be removed as part of implementation so they cannot be selected accidentally.

## Prior Findings

The existing strategy set is not suitable as a live base:

- BeatSpikeReversion variants showed severe same-candle or intrabar bias. Once that bias was removed, performance collapsed.
- PlayBollingerFuturesStrategy had a strong historical backtest but poor dry-run behavior, including large losses relative to the 50 USDT account size.
- SampleStrategy is only an example and is not part of the trading plan.

The new work will not tune around those old signals. It will start from a clean BTC/ETH trend-pullback design.

## Trading Scope

- Exchange mode: Binance USDT-margined futures.
- Margin mode: isolated.
- Pairs: BTC/USDT:USDT and ETH/USDT:USDT only.
- Trade directions: long and short.
- Main timeframe: 15m.
- Informative timeframe: 4h.
- Initial capital assumption: 50 USDT.
- Maximum concurrent positions: 1.
- Dry-run first. No direct live deployment is part of the initial implementation.

Meme coins and broad rotating pairlists are explicitly out of scope.

## Strategy Architecture

Create a new strategy named `BtcEth15mTrendPullbackStrategy`.

The strategy uses the 4h timeframe only as a regime filter and uses the 15m timeframe for entries and exits.

4h long regime:

- 4h close is above EMA50.
- 4h EMA50 is above EMA200.
- Only long entries are allowed.

4h short regime:

- 4h close is below EMA50.
- 4h EMA50 is below EMA200.
- Only short entries are allowed.

Neutral regime:

- If neither long nor short regime is active, the strategy opens no new trades.

## Entry Logic

The strategy should trade trend pullbacks, not raw breakouts or mean reversion against the higher-timeframe trend.

Long entry candidates:

- 4h regime is long.
- 15m price has pulled back near EMA20 or EMA50.
- 15m momentum is recovering, for example RSI crosses back above a neutral threshold such as 45 or 50.
- ATR is not abnormally expanded relative to recent volatility, to avoid chasing late spikes.
- Volume is not unusually low, to reduce thin-market false signals.

Short entry candidates:

- 4h regime is short.
- 15m price has bounced near EMA20 or EMA50.
- 15m momentum is weakening, for example RSI crosses back below a neutral threshold.
- ATR and volume filters pass.

The exact thresholds may be tuned conservatively during implementation, but the implementation must preserve the design intent: 4h direction first, 15m pullback second, risk control always.

## Exit Logic

Initial exits:

- Use an ATR-based stop, initially around 1.8x to 2.2x 15m ATR from entry.
- The stop distance is part of position sizing and must not be treated separately from risk.

Profit protection:

- Add a first profit-protection behavior around 1R to 1.5R, either by tightening the stop or using a conservative trailing mechanism supported by Freqtrade.
- Let strong trends continue using a trailing stop or an EMA20 failure exit.

Failure exit:

- Add a time-based exit when a trade does not move favorably after a defined number of 15m candles.
- Exit on clear 15m trend failure, such as price closing back through the relevant moving average after entry.

## Risk Management

The strategy is designed for a 50 USDT account.

- Target risk per trade: about 0.25 USDT, or 0.5% of the account.
- Maximum strategy target drawdown: 7%.
- Hard account drawdown stop: no new entries after 10% drawdown from the configured starting balance.
- Maximum open trades: 1.
- Leverage cap: start with 5x.
- If exchange minimum notional constraints block valid BTC/ETH orders, implementation may raise the cap to 8x or 10x, but only to satisfy order sizing. Risk per trade must remain capped by the stop distance and risk budget.

Leverage is a sizing tool, not the source of risk appetite.

## Configuration

Create a dedicated config for this strategy, for example:

- `user_data/config_btc_eth_15m_trend.json`

The implementation must not overwrite the existing `user_data/config.json`.

The dedicated config should include:

- `dry_run: true`.
- `trading_mode: futures`.
- `margin_mode: isolated`.
- Static BTC/ETH pairlist.
- `max_open_trades: 1`.
- Initial dry-run wallet aligned to 50 USDT.
- Strategy name `BtcEth15mTrendPullbackStrategy`.

Docker or compose changes should use a dedicated service or clearly scoped config path if needed, without disturbing unrelated user modifications.

## Data Requirements

Required data:

- BTC/USDT:USDT futures 15m candles.
- ETH/USDT:USDT futures 15m candles.
- BTC/USDT:USDT futures 4h candles.
- ETH/USDT:USDT futures 4h candles.

Existing 1m data may be retained for finer validation, but the initial strategy is designed and evaluated on 15m plus 4h.

## Cleanup Scope

Remove old strategy files:

- `user_data/strategies/BeatSpikeReversion*.py`
- `user_data/strategies/play_bollinger_futures_strategy.py`
- `user_data/strategies/sample_strategy.py`

Remove stale backtest artifacts:

- All files under `user_data/backtest_results/` except `.gitkeep`.
- The old `user_data/backtest_results/tmp_multi/` directory and its contents.

Do not remove:

- Market data under `user_data/data/`.
- Existing config files unless a later approved step explicitly changes them.
- Unrelated user edits already present in the working tree.

## Validation Plan

The implementation is not considered ready until these checks have been run or explicitly reported as blocked:

- Unit tests for indicator population and entry/exit gating.
- Backtest on BTC and ETH together.
- Backtest or analysis split into at least two periods, such as train and validation windows.
- `lookahead-analysis` to detect future leakage.
- `recursive-analysis` to detect unstable recursive indicators.
- Review of BTC-only and ETH-only results, not only combined aggregate results.

Acceptance targets:

- Maximum drawdown below 10%.
- Prefer target drawdown below 7%.
- Profit factor should be stable above 1.2 across validation views before considering dry-run.
- Trade count must be high enough to avoid relying on a tiny sample.
- No same-candle or informative timeframe leakage.

Backtest success does not authorize live trading. The next step after passing validation is dry-run observation.

## Out of Scope

- Live trading activation.
- Meme coin pairlists.
- Reinforcement learning or FreqAI.
- High-frequency scalping below 15m.
- Reusing BeatSpike or PlayBollinger signals as the new strategy foundation.
