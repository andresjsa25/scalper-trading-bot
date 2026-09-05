"""
Descarga histórico OHLCV real desde BingX para ADA, LINK, BNB (15m/1h/4h --
15m/1h para V1, 1h/4h para V5), para comparar las dos estrategias en estos
3 activos nuevos pedidos por el usuario (2026-08-04). Script separado de
fetch_data.py (que cubre los símbolos ya en config.SYMBOLS) para no tocar
esa lista ni el bot en vivo.
"""
import os
import sys
from datetime import datetime, timedelta, timezone

import ccxt
import pandas as pd

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import config
from fetch_data import fetch_ohlcv_paginated, _ms

NEW_SYMBOLS = ["ADA/USDT:USDT", "LINK/USDT:USDT", "BNB/USDT:USDT"]
TIMEFRAMES = ["15m", "1h", "4h"]


def main():
    os.makedirs(config.DATA_DIR, exist_ok=True)
    exchange = ccxt.bingx({"enableRateLimit": True, "options": {"defaultType": config.MARKET_TYPE}})
    exchange.load_markets()

    since_dt = datetime.now(timezone.utc) - timedelta(days=int(config.HISTORY_YEARS * 365))
    since_ms = _ms(since_dt)

    for symbol in NEW_SYMBOLS:
        print(f"\n=== {symbol} (desde {since_dt.date()}) ===")
        for tf in TIMEFRAMES:
            print(f"Descargando OHLCV {tf}...")
            df = fetch_ohlcv_paginated(exchange, symbol, tf, since_ms)
            fname = symbol.replace("/", "_").replace(":", "_")
            path = os.path.join(config.DATA_DIR, f"{fname}_{tf}.csv")
            df.to_csv(path, index=False)
            print(f"  {len(df)} velas guardadas en {path}")
            if len(df) > 0:
                print(f"  Rango: {df['datetime'].iloc[0]} -> {df['datetime'].iloc[-1]}")


if __name__ == "__main__":
    main()
