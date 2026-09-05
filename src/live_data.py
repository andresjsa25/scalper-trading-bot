"""Actualiza los CSV 'vivo' de cada símbolo/timeframe con velas nuevas desde
BingX, partiendo del histórico ya descargado en data/ la primera vez.
Mismo criterio que fibo-reversal-bot/src/paper_trading.py::_update_live_data."""
import os
import sys

import pandas as pd

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from fetch_data import fetch_ohlcv_paginated

LIVE_DATA_DIR = os.path.join(config.DATA_DIR, "live")


def update_live_data(exchange, symbol: str, timeframe: str) -> pd.DataFrame:
    os.makedirs(LIVE_DATA_DIR, exist_ok=True)
    fname = symbol.replace("/", "_").replace(":", "_")
    live_path = os.path.join(LIVE_DATA_DIR, f"{fname}_{timeframe}.csv")
    original_path = os.path.join(config.DATA_DIR, f"{fname}_{timeframe}.csv")

    # Si el archivo "vivo" esta vacio o corrupto (visto en vivo 2026-08-26:
    # ETH_USDT_USDT_1h.csv quedo en 0 bytes desde el 2026-08-12, probablemente
    # por un crash a mitad de una escritura anterior -- el bot vino
    # crasheando en silencio en CADA ciclo desde entonces, sin volver a
    # guardar el estado) se cae al original en vez de tirar una excepcion sin
    # atajar que tumba todo run_live_trading.py.
    df = None
    if os.path.exists(live_path) and os.path.getsize(live_path) > 0:
        try:
            df = pd.read_csv(live_path)
        except (pd.errors.EmptyDataError, pd.errors.ParserError) as e:
            print(f"[live_data] {live_path} esta corrupto ({e}) -- recuperando desde el original.")
            df = None
    if df is None:
        df = pd.read_csv(original_path)
    df["datetime"] = pd.to_datetime(df["datetime"], utc=True)
    since_ms = int(df["timestamp"].max()) + 1

    new_rows = fetch_ohlcv_paginated(exchange, symbol, timeframe, since_ms)
    if len(new_rows) > 0:
        df = pd.concat([df, new_rows], ignore_index=True)
        df = df.drop_duplicates(subset="timestamp").sort_values("timestamp").reset_index(drop=True)

    # Escritura atomica: a un archivo temporal y despues os.replace() (atomico
    # tanto en Windows como en POSIX) -- para que un crash/corte de luz a
    # mitad de la escritura no vuelva a dejar el CSV en 0 bytes como paso con
    # ETH.
    tmp_path = live_path + ".tmp"
    df.to_csv(tmp_path, index=False)
    os.replace(tmp_path, live_path)
    return df
