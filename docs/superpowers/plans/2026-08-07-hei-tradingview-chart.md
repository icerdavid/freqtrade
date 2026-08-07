# HEI TradingView-style Kline Viewer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local HEI/USDT futures chart viewer with TradingView-style native pan/zoom and lazy access to every completed candle stored in the local Feather files.

**Architecture:** A small Python standard-library HTTP server exposes a validated, chunked candle API backed by cached pandas DataFrames. A separate page module renders a pinned TradingView Lightweight Charts client that owns its viewport, restores the logical range after prepending older candles, and never uses the legacy external position slider.

**Tech Stack:** Python 3.11, pandas/pyarrow, `http.server`, pytest, TradingView Lightweight Charts 4.2.3, existing Docker Compose image.

---

## File structure

- Create `scripts/hei_kline_viewer/__init__.py`: package marker and public module boundary.
- Create `scripts/hei_kline_viewer/data.py`: timeframe allowlist, Feather loading, validation, cached data access, and candle chunk serialization.
- Create `scripts/hei_kline_viewer/page.py`: standalone chart markup and JavaScript interaction logic.
- Create `scripts/hei_kline_viewer/server.py`: request parsing, JSON/HTML responses, CLI, and server lifecycle.
- Create `scripts/hei_kline_viewer/README.md`: direct and Docker launch commands plus interaction help.
- Create `tests/scripts/test_hei_kline_data.py`: deterministic candle query tests.
- Create `tests/scripts/test_hei_kline_page.py`: regression checks for native interaction and lazy loading behavior.
- Create `tests/scripts/test_hei_kline_server.py`: HTTP routing and validation tests using a temporary server.
- Delete `scripts/create_hei_kline_chart.py` only after the replacement passes automated and browser checks.
- Delete `user_data/backtest_results/hei_kline_chart.html` only after the replacement passes automated and browser checks.

### Task 1: Candle data store

**Files:**
- Create: `scripts/hei_kline_viewer/__init__.py`
- Create: `scripts/hei_kline_viewer/data.py`
- Create: `tests/scripts/test_hei_kline_data.py`

- [ ] **Step 1: Write failing tests for validation, latest chunks, historical chunks, ordering, deduplication, and boundaries**

Create a temporary Feather dataset with duplicate timestamps and deliberately reversed rows. Exercise this public API:

```python
from scripts.hei_kline_viewer.data import CandleStore, QueryError


def test_latest_chunk_is_sorted_unique_and_reports_more(tmp_path):
    write_test_feather(tmp_path, rows=8, reversed_order=True, duplicate_last=True)
    store = CandleStore(tmp_path, {"15m": "hei-15m.feather"}, max_limit=5)

    result = store.query("15m", limit=3)

    assert [item["time"] for item in result["candles"]] == [300, 360, 420]
    assert result["has_more"] is True


def test_before_is_exclusive_and_oldest_chunk_has_no_more(tmp_path):
    write_test_feather(tmp_path, rows=8)
    store = CandleStore(tmp_path, {"15m": "hei-15m.feather"}, max_limit=5)

    result = store.query("15m", before=180, limit=3)

    assert [item["time"] for item in result["candles"]] == [0, 60, 120]
    assert result["has_more"] is False


@pytest.mark.parametrize("timeframe", ["5m", "../secret", "1m/../../x"])
def test_unknown_timeframe_is_rejected(tmp_path, timeframe):
    store = CandleStore(tmp_path, {"15m": "hei-15m.feather"})
    with pytest.raises(QueryError, match="Unsupported timeframe"):
        store.query(timeframe)


@pytest.mark.parametrize("limit", [0, -1, 5001])
def test_limit_outside_bounds_is_rejected(tmp_path, limit):
    store = CandleStore(tmp_path, {"15m": "hei-15m.feather"}, max_limit=5000)
    with pytest.raises(QueryError, match="limit"):
        store.query("15m", limit=limit)
```

- [ ] **Step 2: Run the data tests and verify RED**

Run:

```bash
pytest -q tests/scripts/test_hei_kline_data.py
```

Expected: collection fails because `scripts.hei_kline_viewer.data` does not exist.

- [ ] **Step 3: Implement the minimal validated data store**

Implement these interfaces in `data.py`:

```python
TIMEFRAME_FILES = {
    "1m": "HEI_USDT_USDT-1m-futures.feather",
    "15m": "HEI_USDT_USDT-15m-futures.feather",
    "1h": "HEI_USDT_USDT-1h-futures.feather",
    "2h": "HEI_USDT_USDT-2h-futures.feather",
    "4h": "HEI_USDT_USDT-4h-futures.feather",
    "1d": "HEI_USDT_USDT-1d-futures.feather",
}


class QueryError(ValueError):
    pass


class CandleStore:
    def __init__(self, data_dir: Path, files: Mapping[str, str] = TIMEFRAME_FILES,
                 max_limit: int = 5000) -> None:
        self.data_dir = data_dir
        self.files = dict(files)
        self.max_limit = max_limit
        self._frames: dict[str, pd.DataFrame] = {}

    def query(self, timeframe: str, *, before: int | None = None,
              limit: int = 1500) -> dict[str, object]:
        if timeframe not in self.files:
            raise QueryError(f"Unsupported timeframe: {timeframe}")
        if not 1 <= limit <= self.max_limit:
            raise QueryError(f"limit must be between 1 and {self.max_limit}")
        frame = self._load(timeframe)
        eligible = frame if before is None else frame[frame["time"] < before]
        chunk = eligible.tail(limit)
        return {
            "timeframe": timeframe,
            "candles": chunk[["time", "open", "high", "low", "close", "volume"]]
                .to_dict("records"),
            "has_more": len(eligible) > len(chunk),
        }
```

`_load()` must read only the allowlisted filename, convert `date` to integer UTC seconds, select OHLCV columns, sort by `time`, drop duplicate timestamps keeping the final saved row, cast numeric values to Python-compatible values, and cache the normalized frame.

- [ ] **Step 4: Run the data tests and verify GREEN**

Run:

```bash
pytest -q tests/scripts/test_hei_kline_data.py
```

Expected: all data tests pass with no warnings.

- [ ] **Step 5: Commit the data layer**

```bash
git add scripts/hei_kline_viewer/__init__.py scripts/hei_kline_viewer/data.py tests/scripts/test_hei_kline_data.py
git commit -m "feat: add chunked HEI candle store"
```

### Task 2: TradingView-style page

**Files:**
- Create: `scripts/hei_kline_viewer/page.py`
- Create: `tests/scripts/test_hei_kline_page.py`

- [ ] **Step 1: Write failing regression tests for the page contract**

```python
from scripts.hei_kline_viewer.page import render_page


def test_page_uses_native_chart_navigation_without_legacy_slider():
    html = render_page()
    assert 'type="range"' not in html
    assert "handleScroll" in html
    assert "pressedMouseMove: true" in html
    assert "handleScale" in html
    assert "axisPressedMouseMove: true" in html
    assert "pinch: true" in html


def test_page_lazy_loads_and_preserves_logical_viewport():
    html = render_page()
    assert "subscribeVisibleLogicalRangeChange" in html
    assert "loadOlder" in html
    assert "oldRange.from + added" in html
    assert "oldRange.to + added" in html
    assert "scrollToRealTime" in html


def test_page_exposes_all_requested_timeframes_and_ohlcv():
    html = render_page()
    for timeframe in ("1m", "15m", "1h", "2h", "4h", "1d"):
        assert f">{timeframe}<" in html
    for field in ("O", "H", "L", "C", "V"):
        assert f'data-field="{field}"' in html
```

- [ ] **Step 2: Run the page tests and verify RED**

Run:

```bash
pytest -q tests/scripts/test_hei_kline_page.py
```

Expected: collection fails because `page.py` does not exist.

- [ ] **Step 3: Implement the chart page and native interaction**

`render_page()` returns a complete UTF-8 HTML document containing:

```javascript
const chart = LightweightCharts.createChart(chartRoot, {
  autoSize: true,
  handleScroll: {
    mouseWheel: true,
    pressedMouseMove: true,
    horzTouchDrag: true,
    vertTouchDrag: true,
  },
  handleScale: {
    axisPressedMouseMove: true,
    mouseWheel: true,
    pinch: true,
  },
  kineticScroll: { mouse: true, touch: true },
  crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
  timeScale: { timeVisible: true, secondsVisible: false, barSpacing: 8 },
});
```

Initial loading and historical prepending must use these state transitions:

```javascript
async function loadInitial(timeframe) {
  state = { timeframe, candles: [], loading: false, hasMore: true };
  const payload = await requestCandles(timeframe, null, INITIAL_LIMIT);
  state.candles = payload.candles;
  state.hasMore = payload.has_more;
  applySeriesData();
  const total = state.candles.length;
  chart.timeScale().setVisibleLogicalRange({
    from: Math.max(0, total - INITIAL_VISIBLE),
    to: total + 5,
  });
}

async function loadOlder() {
  if (state.loading || !state.hasMore || state.candles.length === 0) return;
  state.loading = true;
  const oldRange = chart.timeScale().getVisibleLogicalRange();
  const before = state.candles[0].time;
  const payload = await requestCandles(state.timeframe, before, PAGE_LIMIT);
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
  state.loading = false;
}

chart.timeScale().subscribeVisibleLogicalRangeChange((range) => {
  if (range && range.from < 100) loadOlder();
});
```

`applySeriesData()` maps the same candle array to both candlesticks and volume, coloring volume by close/open. Crosshair callbacks update a compact OHLCV strip. The page must include a visible loading/error status, six timeframe buttons, a “回到最新” button calling `scrollToRealTime()`, responsive sizing, and no external position slider.

- [ ] **Step 4: Run the page tests and verify GREEN**

Run:

```bash
pytest -q tests/scripts/test_hei_kline_page.py
```

Expected: all page contract tests pass.

- [ ] **Step 5: Commit the page**

```bash
git add scripts/hei_kline_viewer/page.py tests/scripts/test_hei_kline_page.py
git commit -m "feat: add TradingView-style HEI chart page"
```

### Task 3: Local candle API and CLI server

**Files:**
- Create: `scripts/hei_kline_viewer/server.py`
- Create: `tests/scripts/test_hei_kline_server.py`

- [ ] **Step 1: Write failing HTTP tests**

Start the server on port `0` in a background thread with an injected temporary `CandleStore`, then test real HTTP responses:

```python
def test_root_returns_chart_page(running_server):
    response = urlopen(f"{running_server}/")
    assert response.status == 200
    assert response.headers["Content-Type"].startswith("text/html")
    assert b"LightweightCharts" in response.read()


def test_candle_endpoint_returns_json_chunk(running_server):
    response = urlopen(f"{running_server}/api/candles?timeframe=15m&limit=2")
    payload = json.load(response)
    assert [candle["time"] for candle in payload["candles"]] == [360, 420]


def test_bad_query_returns_400_json(running_server):
    with pytest.raises(HTTPError) as error:
        urlopen(f"{running_server}/api/candles?timeframe=../secret&limit=2")
    assert error.value.code == 400
    assert json.load(error.value)["error"].startswith("Unsupported timeframe")


def test_unknown_route_returns_404(running_server):
    with pytest.raises(HTTPError) as error:
        urlopen(f"{running_server}/missing")
    assert error.value.code == 404
```

- [ ] **Step 2: Run the server tests and verify RED**

Run:

```bash
pytest -q tests/scripts/test_hei_kline_server.py
```

Expected: collection fails because `server.py` does not exist.

- [ ] **Step 3: Implement the HTTP handler and command line entry point**

Expose these interfaces:

```python
def create_server(host: str, port: int, store: CandleStore) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/":
                return self._send(HTTPStatus.OK, render_page().encode(), "text/html; charset=utf-8")
            if parsed.path != "/api/candles":
                return self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
            try:
                params = parse_qs(parsed.query)
                timeframe = require_single(params, "timeframe")
                limit = parse_int(params, "limit", default=1500)
                before = parse_optional_int(params, "before")
                payload = store.query(timeframe, before=before, limit=limit)
            except QueryError as exc:
                return self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return self._send_json(HTTPStatus.OK, payload)

        def log_message(self, format: str, *args: object) -> None:
            return

    return ThreadingHTTPServer((host, port), Handler)
```

The CLI must accept `--host`, `--port`, and `--data-dir`, verify that every allowlisted Feather file exists before serving, print the exact local URL, and shut down cleanly on Ctrl-C. JSON responses must use UTF-8, explicit content length, `Cache-Control: no-store`, and `application/json`.

- [ ] **Step 4: Run the server tests and verify GREEN**

Run:

```bash
pytest -q tests/scripts/test_hei_kline_server.py
```

Expected: all HTTP tests pass without leaked threads or warnings.

- [ ] **Step 5: Commit the server**

```bash
git add scripts/hei_kline_viewer/server.py tests/scripts/test_hei_kline_server.py
git commit -m "feat: serve HEI candles with lazy history API"
```

### Task 4: Runtime documentation and end-to-end verification

**Files:**
- Create: `scripts/hei_kline_viewer/README.md`
- Delete after verification: `scripts/create_hei_kline_chart.py`
- Delete after verification: `user_data/backtest_results/hei_kline_chart.html`

- [ ] **Step 1: Document direct and Docker startup**

Document these exact commands:

```bash
python3 -m scripts.hei_kline_viewer.server --host 127.0.0.1 --port 8765
```

```bash
docker compose run --rm -p 8765:8765 --entrypoint python freqtrade \
  -m scripts.hei_kline_viewer.server --host 0.0.0.0 --port 8765
```

Then open `http://127.0.0.1:8765`. Describe drag, wheel zoom, axis scaling, timeframe switching, crosshair OHLCV, automatic older-history loading, and “回到最新”.

- [ ] **Step 2: Run the focused and full relevant test suites**

Run:

```bash
pytest -q tests/scripts/test_hei_kline_data.py tests/scripts/test_hei_kline_page.py tests/scripts/test_hei_kline_server.py
```

Expected: all tests pass.

Run:

```bash
python3 -m compileall -q scripts/hei_kline_viewer
```

Expected: exit code 0 with no output.

- [ ] **Step 3: Verify the real local data API**

Start the server against `user_data/data/binance/futures`, then request:

```bash
curl -fsS "http://127.0.0.1:8765/api/candles?timeframe=15m&limit=3"
curl -fsS "http://127.0.0.1:8765/api/candles?timeframe=1m&before=1739437380&limit=3"
```

Expected: the first response contains three latest ascending candles; the historical query contains only timestamps lower than `before`, with no duplicate timestamps.

- [ ] **Step 4: Browser-check the original failure mode**

At `http://127.0.0.1:8765` verify:

1. Default `15m` view shows approximately 120 distinct candles.
2. Dragging left keeps the same candle width and does not jump back to the latest candle.
3. Reaching the loaded left edge prepends older candles without moving the visible window.
4. Mouse wheel, bottom time axis, and right price axis all scale independently.
5. Each timeframe loads, and crosshair OHLCV matches the selected candle.

- [ ] **Step 5: Remove the superseded static implementation**

Only after Steps 2–4 pass, remove the old generator and generated HTML with an explicit patch so the local Feather data remains untouched:

```text
Delete scripts/create_hei_kline_chart.py
Delete user_data/backtest_results/hei_kline_chart.html
```

- [ ] **Step 6: Re-run verification after cleanup**

Run:

```bash
pytest -q tests/scripts/test_hei_kline_data.py tests/scripts/test_hei_kline_page.py tests/scripts/test_hei_kline_server.py
python3 -m compileall -q scripts/hei_kline_viewer
git diff --check
```

Expected: all tests pass, compilation succeeds, and `git diff --check` reports no whitespace errors.

- [ ] **Step 7: Commit runtime documentation and cleanup**

```bash
git add scripts/hei_kline_viewer/README.md scripts/create_hei_kline_chart.py
git add -f user_data/backtest_results/hei_kline_chart.html
git commit -m "docs: document HEI chart viewer runtime"
```

If the generated HTML was ignored and never tracked, omit it from `git add`; confirm its absence directly instead.
