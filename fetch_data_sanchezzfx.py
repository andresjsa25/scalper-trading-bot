"""
Descarga histórico OHLCV real desde BingX (público, sin API key) para los
13 símbolos que están LIVE ahora mismo en run_live_trading.py, en 4
temporalidades (5m/15m/1h/4h) -- necesarias para el backtest de la
estrategia SANCHEZZFX (niveles de sesión + liquidity sweep + envolvente,
ver src/strategy_sanchezzfx.py).

Script standalone, no importa nada de run_live_trading.py ni de
live_trading.py -- no toca el bot en vivo, solo lee datos de mercado
públicos y los guarda en data/. Sobreescribe los CSV existentes con datos
frescos hasta hoy.
"""
import os
import sys
from datetime import datetime, timedelta, timezone

import ccxt

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import config
from fetch_data import fetch_ohlcv_paginated, _ms, LAUNCH_DATES

# Los 13 símbolos live en run_live_trading.py (V1_LIVE_CONFIG) al 2026-08-22.
SYMBOLS = [
    "NCCOXAG2USD/USDT:USDT", "NCSISP5002USD/USDT:USDT", "NCSINASDAQ1002USD/USDT:USDT",
    "NCCO1OILBRENT2USD/USDT:USDT", "XAUT/USDT:USDT", "NCSKAMZN2USD/USDT:USDT",
    "ADA/USDT:USDT", "BNB/USDT:USDT", "NCSKAAPL2USD/USDT:USDT",
    "ETH/USDT:USDT", "HYPE/USDT:USDT", "SOL/USDT:USDT", "BTC/USDT:USDT",
]
TIMEFRAMES = ["5m", "15m", "1h", "4h"]

DEFAULT_HISTORY_DAYS = int(config.HISTORY_YEARS * 365)

# BingX no retiene velas de 5m/15m tan atrás como 1h/4h -- pedir 1.5 años
# de 5m para BTC/ETH/SOL/ADA/BNB/HYPE/XAUT devolvió 0 velas (el retry de
# fetch_ohlcv_paginated se agota antes de llegar a donde sí hay datos).
# Comprobado empíricamente: BingX solo tiene ~6 semanas de 5m y ~100 días
# de 15m disponibles para estos símbolos, así que se pide un rango que sí
# exista en vez de repetir el fallo.
TF_MAX_LOOKBACK_DAYS = {"5m": 60, "15m": 120}


def main():
    os.makedirs(config.DATA_DIR, exist_ok=True)
    exchange = ccxt.bingx({"enableRateLimit": True, "options": {"defaultType": config.MARKET_TYPE}})
    exchange.load_markets()

    for symbol in SYMBOLS:
        base_since_dt = LAUNCH_DATES.get(symbol) or (
            datetime.now(timezone.utc) - timedelta(days=DEFAULT_HISTORY_DAYS)
        )
        print(f"\n=== {symbol} (desde {base_since_dt.date()}) ===")

        for tf in TIMEFRAMES:
            cap_days = TF_MAX_LOOKBACK_DAYS.get(tf)
            since_dt = base_since_dt
            if cap_days is not None:
                cap_dt = datetime.now(timezone.utc) - timedelta(days=cap_days)
                since_dt = max(base_since_dt, cap_dt)
            since_ms = _ms(since_dt)
            print(f"  Descargando OHLCV {tf} (desde {since_dt.date()})...")
            df = fetch_ohlcv_paginated(exchange, symbol, tf, since_ms)
            fname = symbol.replace("/", "_").replace(":", "_")
            path = os.path.join(config.DATA_DIR, f"{fname}_{tf}.csv")
            df.to_csv(path, index=False)
            print(f"    {len(df)} velas guardadas en {path}")
            if len(df) > 0:
                print(f"    Rango: {df['datetime'].iloc[0]} -> {df['datetime'].iloc[-1]}")


if __name__ == "__main__":
    main()
