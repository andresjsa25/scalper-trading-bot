"""
Descarga histórico OHLCV 4h desde BingX para NASDAQ100, GOOGL, META, NVDA
-- hace falta para poder correr V5 (Fibonacci, 1h/4h) y V10 (BB+RSI,
1h/4h) sobre estos 4 activos, que hasta ahora solo tenían 15m/1h
(fetch_data_stocks_test.py). Mismos 8 meses pedidos que las corridas
anteriores; acá sí es esperable que se logren completos (el límite de
retención de ~100 días que vimos en 15m no aplica a 4h, igual que ya
pasaba con NASDAQ100 en 1h).

Uso:
    python fetch_data_stocks_4h.py
"""
import os
import sys
from datetime import datetime, timedelta, timezone

import ccxt

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import config
from fetch_data import fetch_ohlcv_paginated, _ms

TEST_SYMBOLS = [
    "NCSINASDAQ1002USD/USDT:USDT",
    "NCSKGOOGL2USD/USDT:USDT",
    "NCSKMETA2USD/USDT:USDT",
    "NCSKNVDA2USD/USDT:USDT",
]
HISTORY_DAYS = 8 * 30


def main():
    os.makedirs(config.DATA_DIR, exist_ok=True)
    exchange = ccxt.bingx({"enableRateLimit": True, "options": {"defaultType": config.MARKET_TYPE}})
    exchange.load_markets()

    since_dt = datetime.now(timezone.utc) - timedelta(days=HISTORY_DAYS)
    since_ms = _ms(since_dt)

    for symbol in TEST_SYMBOLS:
        print(f"\n=== {symbol} (pedido desde {since_dt.date()}) ===")
        df = fetch_ohlcv_paginated(exchange, symbol, "4h", since_ms)
        fname = symbol.replace("/", "_").replace(":", "_")
        path = os.path.join(config.DATA_DIR, f"{fname}_4h.csv")
        df.to_csv(path, index=False)
        print(f"  {len(df)} velas guardadas en {path}")
        if len(df) > 0:
            print(f"  Rango REAL logrado: {df['datetime'].iloc[0]} -> {df['datetime'].iloc[-1]}")


if __name__ == "__main__":
    main()
