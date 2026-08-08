# HEI/XRP USDT 交互式 K线查看器

这个查看器读取本地 Binance Futures Feather 文件，通过 TradingView Lightweight Charts 显示 HEI/USDT 和 XRP/USDT 永续合约。用户输入的“XPR”在币安实际对应 `XRPUSDT`；币安 USDⓈ-M 合约列表中没有 `XPRUSDT`。查看器只在需要时读取历史分块，因此无需把完整的 1 分钟历史一次装入浏览器。

每根 K 线还会计算并显示：

- 振幅：`high - low`；振幅百分比：`(high - low) / abs(open) × 100%`。
- 布林带：20 根 K 线的收盘价 SMA，中轨上下各 2 倍总体标准差（`ddof=0`）。前 19 根 K 线的布林带为空，不会使用未来数据。

## 直接运行

在仓库根目录执行：

```bash
python3 -m scripts.hei_kline_viewer.server --host 127.0.0.1 --port 8765
```

然后打开 <http://127.0.0.1:8765>。

如果数据不在默认的 `user_data/data/binance/futures`，使用：

```bash
python3 -m scripts.hei_kline_viewer.server \
  --data-dir /absolute/path/to/binance/futures \
  --host 127.0.0.1 \
  --port 8765
```

## Docker 运行

```bash
docker run --rm -p 127.0.0.1:8765:8765 \
  -v "${PWD}:/freqtrade" -w /freqtrade \
  --entrypoint python freqtradeorg/freqtrade:stable \
  -m scripts.hei_kline_viewer.server --host 0.0.0.0 --port 8765
```

然后打开 <http://127.0.0.1:8765>。停止服务时按 `Ctrl-C`。

## 操作

- 在图表主体按住鼠标左键并左右拖动，连续浏览历史。
- 使用滚轮缩放时间范围。
- 拖动底部时间轴调整 K 线密度。
- 拖动右侧价格轴调整纵向比例，双击价格轴恢复自动比例。
- 拖到已加载数据左侧附近时，查看器自动载入更早的 K 线，并保持当前画面不跳动。
- 点击 `1m`、`15m`、`1h`、`2h`、`4h` 或 `1d` 切换周期。
- 点击 `HEI` 或 `XRP` 切换合约。
- 移动十字光标查看所指 K 线的北京时间和 OHLCV。
- 十字光标信息栏同时显示当前 K 线振幅、振幅百分比和布林带宽度百分比；图表叠加显示布林带上轨、中轨和下轨。
- 点击“回到最新”返回本地文件中最新的已完成 K 线。

查看器不会合成正在形成的 K 线，也不会请求或构造未来数据。
