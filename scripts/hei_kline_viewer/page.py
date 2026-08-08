from __future__ import annotations


def render_page() -> str:
    """Return the interactive HEI chart page."""
    return PAGE


PAGE = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>HEI/USDT 合约 K线</title>
  <script src="https://cdn.jsdelivr.net/npm/lightweight-charts@4.2.3/dist/lightweight-charts.standalone.production.js"></script>
  <style>
    :root {
      color-scheme: dark;
      --background: #0b0e11;
      --panel: #12171f;
      --panel-strong: #181e27;
      --text: #d9e1ea;
      --muted: #8894a4;
      --border: #27313d;
      --grid: rgba(136, 148, 164, 0.12);
      --up: #26a69a;
      --down: #ef5350;
      --active: #2962ff;
      --warning: #f0b90b;
    }
    * { box-sizing: border-box; }
    html, body { height: 100%; }
    body {
      margin: 0;
      overflow: hidden;
      background: var(--background);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      font-size: 14px;
    }
    .app {
      display: flex;
      flex-direction: column;
      height: 100%;
      min-height: 480px;
    }
    .toolbar {
      display: flex;
      align-items: center;
      min-height: 48px;
      padding: 7px 10px;
      gap: 12px;
      border-bottom: 1px solid var(--border);
      background: var(--panel);
      flex-wrap: wrap;
    }
    .symbol {
      display: flex;
      align-items: baseline;
      gap: 7px;
      white-space: nowrap;
    }
    .symbol strong { font-size: 16px; font-weight: 600; }
    .contract { color: var(--muted); font-size: 12px; }
    .symbols { display: flex; gap: 3px; }
    .timeframes { display: flex; gap: 3px; }
    button {
      appearance: none;
      border: 1px solid transparent;
      border-radius: 5px;
      background: transparent;
      color: var(--muted);
      padding: 6px 9px;
      font: inherit;
      cursor: pointer;
    }
    button:hover { background: var(--panel-strong); color: var(--text); }
    button:focus-visible { outline: 2px solid var(--active); outline-offset: 1px; }
    button.active { background: rgba(41, 98, 255, 0.18); color: #7aa2ff; }
    .latest {
      margin-left: auto;
      border-color: var(--border);
      color: var(--text);
      white-space: nowrap;
    }
    .ohlcv {
      display: flex;
      align-items: center;
      gap: 9px;
      min-height: 30px;
      padding: 4px 12px;
      border-bottom: 1px solid var(--border);
      background: var(--panel);
      color: var(--muted);
      font-variant-numeric: tabular-nums;
      overflow-x: auto;
      white-space: nowrap;
    }
    .ohlcv b { color: var(--text); font-weight: 500; }
    .range { margin-left: auto; color: var(--muted); font-size: 12px; }
    .chart-shell { position: relative; flex: 1; min-height: 0; }
    #chart { position: absolute; inset: 0; }
    #chart-status {
      position: absolute;
      z-index: 5;
      top: 10px;
      left: 12px;
      max-width: calc(100% - 24px);
      padding: 5px 8px;
      border-radius: 4px;
      background: rgba(18, 23, 31, 0.86);
      color: var(--warning);
      font-size: 12px;
      pointer-events: none;
      opacity: 0;
      transition: opacity 120ms ease;
    }
    #chart-status.visible { opacity: 1; }
    .hint {
      position: absolute;
      z-index: 4;
      left: 12px;
      bottom: 28px;
      color: rgba(217, 225, 234, 0.48);
      font-size: 12px;
      pointer-events: none;
    }
    @media (max-width: 720px) {
      .toolbar { gap: 6px; }
      .symbol { width: 100%; }
      .latest { margin-left: 0; }
      .range { width: 100%; margin-left: 0; }
      .hint { display: none; }
    }
  </style>
</head>
<body>
  <main class="app">
    <header class="toolbar">
      <div class="symbol"><strong id="symbol-label">HEI / USDT</strong><span class="contract">永续合约 · Binance</span></div>
      <nav class="symbols" aria-label="交易品种">
        <button type="button" class="active" data-symbol="HEI">HEI</button>
        <button type="button" data-symbol="XRP">XRP</button>
      </nav>
      <nav class="timeframes" aria-label="K线周期">
        <button type="button" data-timeframe="1m">1m</button>
        <button type="button" class="active" data-timeframe="15m">15m</button>
        <button type="button" data-timeframe="1h">1h</button>
        <button type="button" data-timeframe="2h">2h</button>
        <button type="button" data-timeframe="4h">4h</button>
        <button type="button" data-timeframe="1d">1d</button>
      </nav>
      <button class="latest" id="latest" type="button">回到最新</button>
    </header>
    <section class="ohlcv" aria-label="当前K线数据">
      <span data-field="time">--</span>
      <span>O <b data-field="O">--</b></span>
      <span>H <b data-field="H">--</b></span>
      <span>L <b data-field="L">--</b></span>
      <span>C <b data-field="C">--</b></span>
      <span>V <b data-field="V">--</b></span>
      <span>振幅 <b data-field="R">--</b></span>
      <span>振幅% <b data-field="RP">--</b></span>
      <span>BB宽 <b data-field="BBW">--</b></span>
      <span class="range" id="loaded-range">尚未加载</span>
    </section>
    <section class="chart-shell">
      <div id="chart" role="img" aria-label="HEI USDT 可拖动、可缩放的蜡烛图、布林带和成交量图"></div>
      <div id="chart-status" role="status" aria-live="polite"></div>
      <div class="hint">拖动查看历史 · 滚轮缩放 · 拖动时间轴或价格轴调整比例</div>
    </section>
  </main>
  <script>
    const INITIAL_LIMIT = 1500;
    const PAGE_LIMIT = 2000;
    const INITIAL_VISIBLE = 120;
    const LOAD_THRESHOLD = 100;
    const upColor = '#26a69a';
    const downColor = '#ef5350';
    const chartRoot = document.getElementById('chart');
    const statusElement = document.getElementById('chart-status');
    const loadedRangeElement = document.getElementById('loaded-range');
    const fields = Object.fromEntries(
      Array.from(document.querySelectorAll('[data-field]')).map((element) => [element.dataset.field, element])
    );
    let state = {
      symbol: 'HEI',
      timeframe: '15m',
      candles: [],
      loading: false,
      hasMore: true,
      generation: 0,
    };
    let statusTimer = null;

    function showStatus(message, persistent = false) {
      clearTimeout(statusTimer);
      statusElement.textContent = message;
      statusElement.classList.toggle('visible', Boolean(message));
      if (message && !persistent) {
        statusTimer = setTimeout(() => statusElement.classList.remove('visible'), 1800);
      }
    }

    if (!window.LightweightCharts) {
      showStatus('图表组件加载失败，请检查网络后刷新页面', true);
      throw new Error('图表组件加载失败');
    }

    const chart = LightweightCharts.createChart(chartRoot, {
      autoSize: true,
      layout: { background: { color: '#12171f' }, textColor: '#8894a4' },
      grid: {
        vertLines: { color: 'rgba(136, 148, 164, 0.12)' },
        horzLines: { color: 'rgba(136, 148, 164, 0.12)' },
      },
      rightPriceScale: { borderColor: '#27313d' },
      timeScale: {
        borderColor: '#27313d',
        timeVisible: true,
        secondsVisible: false,
        barSpacing: 8,
        rightOffset: 5,
        fixLeftEdge: false,
        lockVisibleTimeRangeOnResize: true,
      },
      handleScroll: {
        mouseWheel: true,
        pressedMouseMove: true,
        horzTouchDrag: true,
        vertTouchDrag: true,
      },
      handleScale: {
        axisPressedMouseMove: true,
        axisDoubleClickReset: true,
        mouseWheel: true,
        pinch: true,
      },
      kineticScroll: { mouse: true, touch: true },
      crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
      localization: {
        timeFormatter: (time) => formatTime(time, true),
        priceFormatter: (price) => formatPrice(price),
      },
    });

    const candleSeries = chart.addCandlestickSeries({
      upColor,
      downColor,
      borderUpColor: upColor,
      borderDownColor: downColor,
      wickUpColor: upColor,
      wickDownColor: downColor,
      priceLineVisible: true,
    });
    const volumeSeries = chart.addHistogramSeries({
      priceFormat: { type: 'volume' },
      priceScaleId: '',
      lastValueVisible: false,
      priceLineVisible: false,
    });
    const bbUpperSeries = chart.addLineSeries({
      color: '#42a5f5',
      lineWidth: 1,
      title: 'BB上轨',
      priceLineVisible: false,
      lastValueVisible: false,
    });
    const bbMiddleSeries = chart.addLineSeries({
      color: '#fbc02d',
      lineWidth: 1,
      title: 'BB中轨',
      priceLineVisible: false,
      lastValueVisible: false,
    });
    const bbLowerSeries = chart.addLineSeries({
      color: '#42a5f5',
      lineWidth: 1,
      title: 'BB下轨',
      priceLineVisible: false,
      lastValueVisible: false,
    });
    chart.priceScale('').applyOptions({ scaleMargins: { top: 0.80, bottom: 0 } });
    candleSeries.priceScale().applyOptions({ scaleMargins: { top: 0.08, bottom: 0.24 } });

    function formatPrice(value) {
      if (!Number.isFinite(Number(value))) return '--';
      return Number(value).toLocaleString('en-US', {
        minimumFractionDigits: 4,
        maximumFractionDigits: 8,
      });
    }

    function formatVolume(value) {
      if (!Number.isFinite(Number(value))) return '--';
      return new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 2 }).format(value);
    }

    function formatTime(unixSeconds, includeSeconds = false) {
      const options = {
        timeZone: 'Asia/Shanghai',
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
      };
      if (includeSeconds) options.second = '2-digit';
      return new Intl.DateTimeFormat('zh-CN', options).format(new Date(Number(unixSeconds) * 1000));
    }

    async function requestCandles(symbol, timeframe, before, limit) {
      const parameters = new URLSearchParams({ symbol, timeframe, limit: String(limit) });
      if (before !== null) parameters.set('before', String(before));
      const response = await fetch(`/api/candles?${parameters}`, { cache: 'no-store' });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
      return payload;
    }

    function mergeCandles(older, current) {
      const byTime = new Map();
      for (const candle of older) byTime.set(candle.time, candle);
      for (const candle of current) byTime.set(candle.time, candle);
      return Array.from(byTime.values()).sort((left, right) => left.time - right.time);
    }

    function applySeriesData() {
      candleSeries.setData(state.candles.map(({ time, open, high, low, close }) => ({
        time, open, high, low, close,
      })));
      volumeSeries.setData(state.candles.map(({ time, open, close, volume }) => ({
        time,
        value: volume,
        color: close >= open ? 'rgba(38, 166, 154, 0.38)' : 'rgba(239, 83, 80, 0.38)',
      })));
      bbUpperSeries.setData(state.candles.filter(candle => candle.bb_upper !== null).map(candle => ({
        time: candle.time,
        value: candle.bb_upper,
      })));
      bbMiddleSeries.setData(state.candles.filter(candle => candle.bb_middle !== null).map(candle => ({
        time: candle.time,
        value: candle.bb_middle,
      })));
      bbLowerSeries.setData(state.candles.filter(candle => candle.bb_lower !== null).map(candle => ({
        time: candle.time,
        value: candle.bb_lower,
      })));
      updateLoadedRange();
      updateOhlcv(state.candles[state.candles.length - 1] || null);
    }

    function updateLoadedRange() {
      if (!state.candles.length) {
        loadedRangeElement.textContent = '尚未加载';
        return;
      }
      const first = formatTime(state.candles[0].time);
      const last = formatTime(state.candles[state.candles.length - 1].time);
      loadedRangeElement.textContent = `${first} — ${last} · 已载入 ${state.candles.length.toLocaleString()} 根`;
    }

    function updateOhlcv(candle, volumeValue = null) {
      if (!candle) return;
      fields.time.textContent = `${formatTime(candle.time, true)} UTC+8`;
      fields.O.textContent = formatPrice(candle.open);
      fields.H.textContent = formatPrice(candle.high);
      fields.L.textContent = formatPrice(candle.low);
      fields.C.textContent = formatPrice(candle.close);
      fields.V.textContent = formatVolume(volumeValue === null ? candle.volume : volumeValue);
      fields.R.textContent = formatPrice(candle.range);
      fields.RP.textContent = Number.isFinite(Number(candle.range_pct))
        ? `${Number(candle.range_pct).toFixed(2)}%`
        : '--';
      fields.BBW.textContent = Number.isFinite(Number(candle.bb_width_pct))
        ? `${Number(candle.bb_width_pct).toFixed(2)}%`
        : '--';
      const directionColor = candle.close >= candle.open ? upColor : downColor;
      for (const field of ['O', 'H', 'L', 'C']) fields[field].style.color = directionColor;
    }

    function setActiveTimeframe(timeframe) {
      for (const button of document.querySelectorAll('[data-timeframe]')) {
        button.classList.toggle('active', button.dataset.timeframe === timeframe);
      }
    }

    function setActiveSymbol(symbol) {
      for (const button of document.querySelectorAll('[data-symbol]')) {
        button.classList.toggle('active', button.dataset.symbol === symbol);
      }
      document.getElementById('symbol-label').textContent = `${symbol} / USDT`;
      document.getElementById('chart').setAttribute(
        'aria-label', `${symbol} USDT 可拖动、可缩放的蜡烛图、布林带和成交量图`
      );
    }

    async function loadInitial(symbol, timeframe) {
      const generation = state.generation + 1;
      state = { symbol, timeframe, candles: [], loading: true, hasMore: true, generation };
      setActiveSymbol(symbol);
      setActiveTimeframe(timeframe);
      showStatus(`正在加载 ${symbol} ${timeframe} 数据`, true);
      candleSeries.setData([]);
      volumeSeries.setData([]);
      bbUpperSeries.setData([]);
      bbMiddleSeries.setData([]);
      bbLowerSeries.setData([]);
      try {
        const payload = await requestCandles(symbol, timeframe, null, INITIAL_LIMIT);
        if (generation !== state.generation) return;
        state.candles = payload.candles;
        state.hasMore = payload.has_more;
        applySeriesData();
        const total = state.candles.length;
        chart.timeScale().setVisibleLogicalRange({
          from: Math.max(0, total - INITIAL_VISIBLE),
          to: total + 5,
        });
        showStatus('');
      } catch (error) {
        if (generation === state.generation) showStatus(`加载失败：${error.message}`, true);
      } finally {
        if (generation === state.generation) state.loading = false;
      }
    }

    async function loadOlder() {
      if (state.loading || !state.hasMore || state.candles.length === 0) return;
      const generation = state.generation;
      const symbol = state.symbol;
      const timeframe = state.timeframe;
      const before = state.candles[0].time;
      state.loading = true;
      showStatus('正在加载更早数据', true);
      try {
        const payload = await requestCandles(symbol, timeframe, before, PAGE_LIMIT);
        if (generation !== state.generation) return;
        const oldRange = chart.timeScale().getVisibleLogicalRange();
        const merged = mergeCandles(payload.candles, state.candles);
        const added = merged.length - state.candles.length;
        state.candles = merged;
        state.hasMore = payload.has_more;
        applySeriesData();
        if (oldRange && added > 0) {
          chart.timeScale().setVisibleLogicalRange({
            from: oldRange.from + added,
            to: oldRange.to + added,
          });
        }
        showStatus(state.hasMore ? '' : '已到本地历史数据起点');
      } catch (error) {
        if (generation === state.generation) showStatus(`加载失败：${error.message}`, true);
      } finally {
        if (generation === state.generation) state.loading = false;
      }
    }

    chart.timeScale().subscribeVisibleLogicalRangeChange((range) => {
      if (range && range.from < LOAD_THRESHOLD) loadOlder();
    });

    chart.subscribeCrosshairMove((parameter) => {
      if (!parameter.time || !parameter.seriesData) return;
      const candle = parameter.seriesData.get(candleSeries);
      if (!candle) return;
      const volume = parameter.seriesData.get(volumeSeries);
      updateOhlcv(candle, volume ? volume.value : null);
    });

    for (const button of document.querySelectorAll('[data-symbol]')) {
      button.addEventListener('click', () => loadInitial(button.dataset.symbol, state.timeframe));
    }
    for (const button of document.querySelectorAll('[data-timeframe]')) {
      button.addEventListener('click', () => loadInitial(state.symbol, button.dataset.timeframe));
    }
    document.getElementById('latest').addEventListener('click', () => {
      chart.timeScale().scrollToRealTime();
      updateOhlcv(state.candles[state.candles.length - 1] || null);
    });

    loadInitial('HEI', '15m');
  </script>
</body>
</html>
"""
