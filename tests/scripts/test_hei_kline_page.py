from scripts.hei_kline_viewer.page import render_page


def test_page_uses_native_chart_navigation_without_legacy_slider() -> None:
    html = render_page()

    assert 'type="range"' not in html
    assert "handleScroll" in html
    assert "pressedMouseMove: true" in html
    assert "handleScale" in html
    assert "axisPressedMouseMove: true" in html
    assert "pinch: true" in html
    assert "kineticScroll" in html


def test_page_lazy_loads_and_preserves_logical_viewport() -> None:
    html = render_page()

    assert "subscribeVisibleLogicalRangeChange" in html
    assert "getVisibleLogicalRange" in html
    assert "loadOlder" in html
    assert "oldRange.from + added" in html
    assert "oldRange.to + added" in html
    assert "scrollToRealTime" in html


def test_page_exposes_all_requested_timeframes_and_ohlcv() -> None:
    html = render_page()

    for timeframe in ("1m", "15m", "1h", "2h", "4h", "1d"):
        assert f'data-timeframe="{timeframe}"' in html
    for field in ("O", "H", "L", "C", "V"):
        assert f'data-field="{field}"' in html


def test_page_defaults_to_readable_candle_window() -> None:
    html = render_page()

    assert "const INITIAL_VISIBLE = 120" in html
    assert "barSpacing: 8" in html
    assert "total - INITIAL_VISIBLE" in html


def test_page_has_loading_error_and_library_failure_states() -> None:
    html = render_page()

    assert 'id="chart-status"' in html
    assert "正在加载更早数据" in html
    assert "加载失败" in html
    assert "图表组件加载失败" in html
