from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Mapping, Sequence
from urllib.parse import parse_qs, urlparse

from scripts.hei_kline_viewer.data import CandleStore, QueryError, SYMBOL_FILES
from scripts.hei_kline_viewer.page import render_page


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = ROOT / "user_data" / "data" / "binance" / "futures"


def require_single(parameters: Mapping[str, list[str]], name: str) -> str:
    values = parameters.get(name)
    if not values:
        raise QueryError(f"Missing query parameter: {name}")
    if len(values) != 1:
        raise QueryError(f"{name} must appear once")
    return values[0]


def parse_int(
    parameters: Mapping[str, list[str]], name: str, *, default: int
) -> int:
    values = parameters.get(name)
    if not values:
        return default
    if len(values) != 1:
        raise QueryError(f"{name} must appear once")
    try:
        return int(values[0])
    except ValueError as exc:
        raise QueryError(f"{name} must be an integer") from exc


def parse_optional_int(parameters: Mapping[str, list[str]], name: str) -> int | None:
    values = parameters.get(name)
    if not values:
        return None
    if len(values) != 1:
        raise QueryError(f"{name} must appear once")
    try:
        return int(values[0])
    except ValueError as exc:
        raise QueryError(f"{name} must be an integer") from exc


def create_server(
    host: str,
    port: int,
    store: CandleStore,
    *,
    stores: Mapping[str, CandleStore] | None = None,
) -> ThreadingHTTPServer:
    symbol_stores = dict(stores or {"HEI": store})

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/":
                self._send(
                    HTTPStatus.OK,
                    render_page().encode("utf-8"),
                    "text/html; charset=utf-8",
                )
                return
            if parsed.path != "/api/candles":
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
                return

            try:
                parameters = parse_qs(parsed.query, keep_blank_values=True)
                symbol = parameters.get("symbol", ["HEI"])[0]
                if symbol not in symbol_stores:
                    raise QueryError(f"Unsupported symbol: {symbol}")
                timeframe = require_single(parameters, "timeframe")
                limit = parse_int(parameters, "limit", default=1500)
                before = parse_optional_int(parameters, "before")
                payload = symbol_stores[symbol].query(
                    timeframe, before=before, limit=limit
                )
                payload["symbol"] = symbol
            except QueryError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                return

            self._send_json(HTTPStatus.OK, payload)

        def _send_json(self, status: HTTPStatus, payload: object) -> None:
            body = json.dumps(
                payload,
                ensure_ascii=False,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
            self._send(status, body, "application/json; charset=utf-8")

        def _send(self, status: HTTPStatus, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            return

    return ThreadingHTTPServer((host, port), Handler)


def validate_data_files(data_dir: Path) -> None:
    missing = [
        str(data_dir / filename)
        for files in SYMBOL_FILES.values()
        for filename in files.values()
        if not (data_dir / filename).is_file()
    ]
    if missing:
        formatted = "\n".join(f"  - {path}" for path in missing)
        raise QueryError(f"Missing candle files:\n{formatted}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Serve the local HEI futures Kline viewer")
    parser.add_argument("--host", default="127.0.0.1", help="listen address")
    parser.add_argument("--port", type=int, default=8765, help="listen port")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help="directory containing HEI futures Feather files",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    data_dir = arguments.data_dir.expanduser().resolve()
    try:
        validate_data_files(data_dir)
    except QueryError as exc:
        raise SystemExit(str(exc)) from exc

    stores = {
        symbol: CandleStore(data_dir, files)
        for symbol, files in SYMBOL_FILES.items()
    }
    server = create_server(
        arguments.host,
        arguments.port,
        stores["HEI"],
        stores=stores,
    )
    display_host = "127.0.0.1" if arguments.host in {"0.0.0.0", "::"} else arguments.host
    print(f"HEI Kline viewer: http://{display_host}:{server.server_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping HEI Kline viewer.", flush=True)
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
