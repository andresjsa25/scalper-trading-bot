"""
Descarga histórico OHLCV real desde BingX (vía ccxt) para los 10 símbolos
del bot scalper, en 15min (entrada) y 1h (contexto/liquidez).

Para BTC/ETH/XAUT se pide HISTORY_YEARS hacia atrás (igual que
fibo-reversal-bot). Para los sintéticos NCSI/NCCO/NCSK y HYPE se usa su
fecha real de listado en BingX (ya verificada al construir fibo-reversal-bot
-- no se inventa, son las mismas fechas de exchange.load_markets()[...]['info']['launchTime']).

No requiere API key: los datos de mercado son públicos.
"""
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import ccxt
import pandas as pd

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import config

# símbolo -> fecha real de listado en BingX; None = usar HISTORY_YEARS hacia atrás
LAUNCH_DATES = {
    "NCSISP5002USD/USDT:USDT": datetime(2025, 11, 26, tzinfo=timezone.utc),
    "NCSINASDAQ1002USD/USDT:USDT": datetime(2025, 11, 26, tzinfo=timezone.utc),
    "NCCO1OILBRENT2USD/USDT:USDT": datetime(2026, 3, 6, tzinfo=timezone.utc),
    "NCCOXAG2USD/USDT:USDT": datetime(2026, 2, 11, tzinfo=timezone.utc),
    "HYPE/USDT:USDT": datetime(2024, 12, 19, tzinfo=timezone.utc),
    "NCSKAAPL2USD/USDT:USDT": datetime(2025, 11, 13, tzinfo=timezone.utc),
    "NCSKAMZN2USD/USDT:USDT": datetime(2025, 11, 3, tzinfo=timezone.utc),
}


def _ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def fetch_ohlcv_paginated(exchange, symbol: str, timeframe: str, since_ms: int) -> pd.DataFrame:
    """Descarga OHLCV completo paginando (los exchanges limitan velas por llamada)."""
    all_rows = []
    limit = 1000
    cursor = since_ms
    now_ms = _ms(datetime.now(timezone.utc))

    empty_retries = 0
    while cursor < now_ms:
        batch = exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=cursor, limit=limit)
        if not batch:
            empty_retries += 1
            if empty_retries > 24:
                break
            cursor += 15 * 24 * 60 * 60 * 1000  # +15 días en ms
            time.sleep(exchange.rateLimit / 1000)
            continue
        empty_retries = 0
        all_rows.extend(batch)
        last_ts = batch[-1][0]
        if last_ts <= cursor:
            break
        cursor = last_ts + 1
        time.sleep(exchange.rateLimit / 1000)

    df = pd.DataFrame(all_rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = df.drop_duplicates(subset="timestamp").sort_values("timestamp").reset_index(drop=True)
    return df


def main():
    os.makedirs(config.DATA_DIR, exist_ok=True)

    exchange_class = getattr(ccxt, config.EXCHANGE_ID)
    exchange = exchange_class({
        "enableRateLimit": True,
        "options": {"defaultType": config.MARKET_TYPE},
    })
    exchange.load_markets()

    default_since = datetime.now(timezone.utc) - timedelta(days=int(config.HISTORY_YEARS * 365))

    for symbol in config.SYMBOLS:
        since_dt = LAUNCH_DATES.get(symbol, default_since)
        since_ms = _ms(since_dt)
        print(f"\n=== {symbol} (desde {since_dt.date()}) ===")

        for tf in [config.TIMEFRAME_ENTRY, config.TIMEFRAME_CONTEXT]:
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
