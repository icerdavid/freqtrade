# Binance TradFi Stock Perp Momentum Strategy Design

Date: 2026-07-21

## Purpose

Build a new Freqtrade futures strategy that targets the user's current goal: optimize the strategy across Binance stock perpetual contracts, commodity-style TradFi contracts, and stable-quoted futures where useful, with a final three-month backtest profit target above 100%.

This replaces the BTC/ETH-only direction as the active strategy research path. The BTC/ETH strategy is preserved as prior evidence, but it is not considered a valid base because its verified backtests were negative.

The design is aggressive by intent. It treats three-month profit above 100% as a research and backtest optimization target, not as a promise that live trading can reproduce it.

## Prior Findings

The earlier strategy work produced useful constraints:

- BeatSpikeReversion variants were invalid as a live base because their apparent edge depended on same-candle or intrabar bias. After removing that bias, results collapsed.
- PlayBollingerFuturesStrategy had a strong historical backtest but performed poorly in dry-run with a 50 USDT account.
- `BtcEth15mTrendPullbackStrategy` was engineering-clean and passed bias checks, but it failed the trading target: combined, BTC-only, ETH-only, train, and validation views were all negative.

The new strategy must therefore change both the traded universe and the signal family. Small BTC/ETH trend pullbacks are not enough for the requested three-month return target.

## Current Exchange Facts

Binance Futures currently exposes TradFi perpetual contracts through the USDT-margined futures API. A current `fapi/v1/exchangeInfo` check showed 136 trading `TRADIFI_PERPETUAL` symbols, including:

- `INTCUSDT`
- `SNDKUSDT`
- `NVDAUSDT`
- `TSLAUSDT`
- `MSTRUSDT`
- `COINUSDT`
- `HOODUSDT`
- `PLTRUSDT`
- `SOXLUSDT`
- `TQQQUSDT`
- `SQQQUSDT`
- `UVXYUSDT`

Freqtrade/CCXT recognizes these markets with pair names such as:

- `INTC/USDT:USDT`
- `SNDK/USDT:USDT`
- `NVDA/USDT:USDT`
- `SOXL/USDT:USDT`
- `TQQQ/USDT:USDT`
- `SQQQ/USDT:USDT`

Most checked TradFi perpetuals have a minimum notional of 5 USDT, which is compatible with a 50 USDT research account.

## Trading Scope

- Exchange mode: Binance USDT-margined futures.
- Margin mode: isolated.
- Quote and margin asset: USDT by default.
- Main timeframe: 15m.
- Informative timeframe: 1h.
- Optional validation timeframe: 5m detail data if Freqtrade supports it for the selected pairs.
- Initial capital assumption: 50 USDT.
- Maximum concurrent positions: 1 in the first implementation.
- Trade directions: long and short.
- Dry-run first. Live deployment is explicitly out of scope for the initial implementation.

The strategy will not trade meme coins. It may trade high-volatility stock or ETF-style TradFi perpetuals when they are listed as Binance futures markets.

## Candidate Universe

Start with a static, high-volatility TradFi universe:

- Single-stock or stock-like perps: `INTC/USDT:USDT`, `SNDK/USDT:USDT`, `NVDA/USDT:USDT`, `TSLA/USDT:USDT`, `MSTR/USDT:USDT`, `COIN/USDT:USDT`, `HOOD/USDT:USDT`, `PLTR/USDT:USDT`.
- Semiconductor and technology beta perps: `AMD/USDT:USDT`, `MU/USDT:USDT`, `AVGO/USDT:USDT`, `QCOM/USDT:USDT`, `SOXL/USDT:USDT`, `SOXS/USDT:USDT`.
- Index or leveraged ETF-style perps: `QQQ/USDT:USDT`, `SPY/USDT:USDT`, `TQQQ/USDT:USDT`, `SQQQ/USDT:USDT`, `IWM/USDT:USDT`, `TZA/USDT:USDT`, `UVXY/USDT:USDT`.
- Crypto-adjacent equity perps if liquid enough: `MSTR/USDT:USDT`, `COIN/USDT:USDT`, `HOOD/USDT:USDT`.

The first version should use a curated static whitelist rather than an unrestricted dynamic pairlist. The strategy may internally rank symbols, but it should not rotate into low-quality symbols only because they backtested well in a tiny window.

## Strategy Architecture

Create a new strategy named `TradFiStockPerpMomentumStrategy`.

The strategy is a momentum-rotation breakout system:

1. Each pair calculates 1h trend strength and volatility state.
2. Each pair calculates 15m breakout and pullback-confirmation signals.
3. The strategy only enters when the pair's own trend and the 15m trigger align.
4. Position sizing uses ATR stop distance, leverage, and a fixed account risk budget.
5. Exit logic prioritizes fast loss cutting and lets unusually strong momentum run with a trailing stop.

The design intentionally favors momentum and volatility expansion over mean reversion. The requested three-month target is unlikely to be reached by low-frequency conservative trend pullbacks.

## Trend and Regime Logic

Use the 1h timeframe as the main regime filter.

Long regime candidates:

- 1h close is above EMA50.
- 1h EMA20 is above EMA50.
- 1h rate of change over 12 to 24 candles is positive.
- 1h ATR percentage is above a minimum volatility threshold but below an extreme exhaustion threshold.

Short regime candidates:

- 1h close is below EMA50.
- 1h EMA20 is below EMA50.
- 1h rate of change over 12 to 24 candles is negative.
- 1h ATR percentage is above a minimum volatility threshold but below an extreme exhaustion threshold.

Neutral regime:

- No entry when 1h trend direction is mixed.
- No entry when 1h volatility is too compressed to justify leverage.
- No entry immediately after an extreme candle that is likely to mean-revert.

## Entry Logic

The 15m chart controls entry timing.

Long entry candidates:

- 1h long regime is active.
- 15m close breaks above the recent Donchian high or Bollinger upper band.
- 15m volume is above its recent moving average.
- 15m RSI or momentum confirms the breakout.
- ATR-based stop distance allows at least the configured minimum stake and does not imply excessive liquidation risk.

Alternative long pullback entry:

- 1h long regime is active.
- 15m price pulls back to EMA20 or VWAP-style mean and then reclaims it.
- Momentum turns positive before the entry candle closes.

Short entry candidates:

- 1h short regime is active.
- 15m close breaks below the recent Donchian low or Bollinger lower band.
- 15m volume is above its recent moving average.
- 15m RSI or momentum confirms the breakdown.
- ATR-based stop distance allows valid sizing.

The first implementation should include both breakout and pullback-reclaim tags so backtests can show which signal family is actually responsible for profit.

## Rotation and Pair Selection

Freqtrade strategy code cannot perfectly allocate across all symbols without care, so first implementation keeps `max_open_trades` at 1.

To approximate rotation:

- All whitelisted pairs can emit signals.
- `custom_stake_amount` and pair-level filters reject weak or invalid signals.
- The pair with the earliest valid signal gets the one open slot.
- Backtest reports must be decomposed by pair and entry tag.

A later iteration may add explicit pair-ranking or a custom pairlist, but that is not required for the first implementation.

## Exit Logic

Initial stop:

- Use ATR-based stop distance from the entry candle.
- Default starting range: 1.5x to 2.5x 15m ATR.
- Stop distance must feed into position sizing.

Profit-taking:

- At approximately 1R, tighten risk or activate a trailing condition.
- At strong momentum expansion, keep the position open until trailing stop, EMA failure, or momentum failure.
- Avoid tiny fixed ROI exits that cap the upside before a strong trend can pay for losses.

Failure exits:

- Exit if the trade fails to move at least a small positive amount within a defined number of 15m candles.
- Exit long when 15m close loses EMA20/EMA50 depending on the signal type.
- Exit short when 15m close reclaims EMA20/EMA50 depending on the signal type.

Funding and session risk:

- The first version will not use an external earnings calendar.
- It should avoid opening new trades during clearly illiquid or flat windows if candle data shows low volume and low range.
- Backtest reporting must include average duration and holding periods around funding intervals if available.

## Risk Management

The strategy is designed for an initial 50 USDT research wallet.

- Maximum open trades: 1.
- Maximum account drawdown target: 10%.
- Risk per trade starting range: 0.5% to 2.0% of account equity.
- Leverage cap starting range: 5x to 10x.
- Margin mode: isolated.
- Reject trades when ATR stop distance, exchange minimum notional, and leverage would imply a loss larger than the risk budget.
- Stop trading after reaching the hard drawdown threshold.

The requested three-month profit target may require temporarily testing aggressive risk settings. Each aggressive configuration must be reported with its realized max drawdown and trade count. A configuration that reaches 100% profit only by exceeding the 10% drawdown target is not considered fully successful; it is an intermediate research result.

## Configuration

Create a dedicated config:

- `user_data/config_tradfi_stock_perp_momentum.json`

The implementation must not overwrite `user_data/config.json`.

The dedicated config should include:

- `dry_run: true`
- `trading_mode: futures`
- `margin_mode: isolated`
- `stake_currency: USDT`
- `dry_run_wallet: 50`
- Static pair whitelist for the selected TradFi universe
- `max_open_trades: 1`
- Strategy name `TradFiStockPerpMomentumStrategy`

Existing user edits to `Dockerfile`, `docker-compose.yml`, and `ft_client/freqtrade_client/ft_rest_client.py` are out of scope unless the user explicitly asks to change them.

## Data Requirements

Download futures data for all selected pairs:

- 15m candles for strategy operation.
- 1h candles for trend filters.
- Mark or funding data if required by Freqtrade futures backtesting.
- Optional 5m candles for later detail validation.

Primary validation window:

- The latest available three-month window ending at the newest downloaded candle.

Exploration windows:

- At least one earlier three-month window.
- At least one longer train window if enough TradFi data exists.

The final result must clearly label which window is the main three-month result. It must not cherry-pick an old three-month window and present it as the current expected outcome.

## Optimization Plan

Optimization may vary these parameters:

- Candidate universe subset.
- Long-only, short-only, or long/short mode.
- 1h EMA and ROC thresholds.
- 15m breakout channel length.
- Pullback EMA choice.
- ATR stop multiple.
- Trailing stop thresholds.
- Time-stop candle count.
- Risk budget per trade.
- Leverage cap.

Optimization must not introduce lookahead behavior, same-candle cheating, future volatility labels, or pair selection based on future returns inside the validation window.

## Validation Plan

The implementation is not considered successful until these checks are run or explicitly reported as blocked:

- Unit tests for indicator population, pair filtering, entry tags, exit tags, stake sizing, leverage cap, and drawdown guard.
- Docker-backed strategy import test.
- Backtest on the full selected TradFi universe.
- Decomposition by pair, side, and entry tag.
- Latest three-month backtest.
- At least one earlier three-month backtest.
- `lookahead-analysis`.
- `recursive-analysis`.

Primary acceptance target:

- Latest three-month total profit above 100%.

Secondary acceptance targets:

- Maximum drawdown at or below 10%.
- Profit factor above 1.2 in the primary window.
- Trade count high enough that the result is not one lucky trade.
- No detected lookahead bias.
- No meaningful recursive indicator instability.

If no configuration reaches all targets, the report must state the best verified configuration and which target failed. It is better to report that no honest strategy met the goal than to ship a biased or overfit strategy.

## Cleanup Scope

Do not delete existing BTC/ETH strategy files during the design phase.

During implementation, the old BTC/ETH files may be kept as prior research unless the user asks for a clean active-strategy-only workspace. If cleanup is performed, preserve:

- `user_data/data/`
- `user_data/config.json`
- `.gitkeep` files
- unrelated user edits

## Out of Scope

- Live trading activation.
- Real-money recommendation or guarantee.
- External broker integrations outside Binance Futures.
- Meme coin strategies.
- Strategies that depend on hidden future data.
- Manual selection of a profitable backtest interval after seeing all results.
