# HEI/USDT 交互式 K线查看器

这个查看器读取本地 Binance Futures Feather 文件，通过 TradingView Lightweight Charts 显示 HEI/USDT 永续合约。它只在需要时读取历史分块，因此无需把完整的 1 分钟历史一次装入浏览器。

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
docker compose run --rm -p 8765:8765 -v "${PWD}:/freqtrade" \
  --entrypoint python freqtrade \
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
- 移动十字光标查看所指 K 线的北京时间和 OHLCV。
- 点击“回到最新”返回本地文件中最新的已完成 K 线。

查看器不会合成正在形成的 K 线，也不会请求或构造未来数据。
