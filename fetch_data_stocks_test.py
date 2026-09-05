"""
Descarga histórico OHLCV real desde BingX para NASDAQ100 (refresco -- los
datos guardados llegaban hasta el 22/08) + GOOGL, META, NVDA (nuevos),
15m/1h, para el backtesting pedido por el usuario (sep 2026). RUSSELL2000
queda afuera por ahora -- BingX tiene el símbolo pausado para histórico
(NCSIRUSSELL20002USD, error 109415 "is pause currently").

Mismo patrón que fetch_data_new_assets.py: script separado, no toca
config.SYMBOLS ni el bot en vivo.

8 meses pedidos, igual que fetch_data_forex.py -- pero para el timeframe
de entrada (15m) es esperable que BingX devuelva bastante menos: para
NASDAQ100 el histórico real de 15m solo llega a ~3.3 meses atrás (límite
de retención de BingX para estos sintéticos, no un límite nuestro). El
timeframe de contexto (1h) sí suele llegar más atrás. El script imprime el
rango real logrado por símbolo -- se arma el reporte de backtest con el
rango real, no con el pedido.
"""
import os
import sys
from datetime import datetime, timedelta, timezone

import ccxt

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import config
from fetch_data import fetch_ohlcv_paginated, _ms

TEST_SYMBOLS = [
    "NCSINASDAQ1002USD/USDT:USDT",  # refresco
    "NCSKGOOGL2USD/USDT:USDT",
    "NCSKMETA2USD/USDT:USDT",
    "NCSKNVDA2USD/USDT:USDT",
]
TIMEFRAMES = [config.TIMEFRAME_ENTRY, config.TIMEFRAME_CONTEXT]  # 15m, 1h

HISTORY_MONTHS = 8
HISTORY_DAYS = HISTORY_MONTHS * 30


def main():
    os.makedirs(config.DATA_DIR, exist_ok=True)
    exchange = ccxt.bingx({"enableRateLimit": True, "options": {"defaultType": config.MARKET_TYPE}})
    exchange.load_markets()

    since_dt = datetime.now(timezone.utc) - timedelta(days=HISTORY_DAYS)
    since_ms = _ms(since_dt)

    for symbol in TEST_SYMBOLS:
        print(f"\n=== {symbol} (pedido desde {since_dt.date()}) ===")
        for tf in TIMEFRAMES:
            print(f"  Descargando OHLCV {tf}...")
            df = fetch_ohlcv_paginated(exchange, symbol, tf, since_ms)
            fname = symbol.replace("/", "_").replace(":", "_")
            path = os.path.join(config.DATA_DIR, f"{fname}_{tf}.csv")
            df.to_csv(path, index=False)
            print(f"    {len(df)} velas guardadas en {path}")
            if len(df) > 0:
                print(f"    Rango REAL logrado: {df['datetime'].iloc[0]} -> {df['datetime'].iloc[-1]}")


if __name__ == "__main__":
    main()
