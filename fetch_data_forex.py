"""
Descarga histórico REAL de EUR/USD y USD/JPY desde Dukascopy (gratis, sin
cuenta ni API key) para poder backtestear las estrategias del bot en estos
dos pares antes de sumarlos a config.SYMBOLS / V1_LIVE_CONFIG (pedido del
usuario, sep 2026 -- reemplazo de AMZN, sacado por rachas de pérdidas
seguidas en vivo).

Por qué Dukascopy y no BingX: BingX es un exchange de derivados cripto --
lo que en config.SYMBOLS parece "activos tradicionales" (NCSKAAPL2USD,
NCSISP5002USD, etc.) son CFDs sintéticos tokenizados propios de BingX, no
instrumentos de forex reales -- no tiene ni EUR/USD ni USD/JPY listados.
Dukascopy sí publica tick data histórica real y gratuita de los pares
forex principales, sin cuenta ni límite de profundidad, vía un endpoint
HTTP público sin autenticación (ver duka/core/fetch.py).

Se usa la propia función app() del paquete `duka` (misma que usa su CLI)
para la descarga concurrente día por día -- reusa su ThreadPoolExecutor ya
probado en vez de reimplementar la descarga a mano. Se pide en modo TICK
(no en modo vela -c de duka) a propósito: el cálculo de timestamp de vela
de esa librería (duka/core/csv_dumper.py) pasa el dato por
time.mktime()/datetime.fromtimestamp(), que asume la zona horaria LOCAL de
la máquina que corre el script -- en la práctica esa ida y vuelta termina
cancelándose casi siempre, pero no es un supuesto en el que valga la pena
confiar a ciegas para datos que van a alimentar un backtest real de plata
real. En modo TICK, en cambio, el timestamp queda naive-UTC real y sin
ninguna conversión de por medio (confirmado leyendo duka/core/processor.py
-- normalize() arma la fecha directo desde el día UTC + milisegundos). Acá
se arma la vela nosotros mismos con pandas, con UTC explícito de punta a
punta -- mismo criterio que fetch_data.py con BingX.

Precio de la vela: mid = (ask + bid) / 2 (convención estándar para
reconstruir OHLC de forex desde tick data bid/ask).

Volumen: Dukascopy no tiene volumen real de mercado (es un feed agregado
de brokers, no un exchange centralizado) -- la columna "volume" acá es
ask_volume + bid_volume tal como los reporta Dukascopy, un proxy de
actividad, NO comparable en magnitud con el volumen real de BingX en los
CSV de cripto. Sirve igual para estrategias que lo usan de forma relativa
a sí mismo (ver src/indicators/volume.py, add_relative_volume -- se
normaliza contra su propio promedio móvil, no contra un valor absoluto),
pero si se nota comportamiento raro de V6 (order-flow proxy) en estos dos
pares, esta es la primera sospecha a revisar.

Requiere: pip install duka pandas   (no requiere cuenta ni API key)

Uso:
    python fetch_data_forex.py

Puede tardar bastante (son ~1.5 años de tick data de 2 pares) -- va
imprimiendo una barra de progreso de duka por cada símbolo.
"""
import os
import shutil
import sys
import tempfile
from datetime import date, timedelta

import pandas as pd
from duka.app import app as duka_fetch
from duka.core.utils import TimeFrame

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import config

# símbolo interno (mismo criterio de nombre de archivo que fetch_data.py,
# reemplazando "/" por "_") -> ticker de Dukascopy
FOREX_SYMBOLS = {
    "EUR/USD": "EURUSD",
    "USD/JPY": "USDJPY",
}

# timeframe del bot (config.py) -> regla de resample de pandas
RESAMPLE_RULE = {
    config.TIMEFRAME_ENTRY: "15min",
    config.TIMEFRAME_CONTEXT: "1h",
}

# Para forex se pide menos profundidad que config.HISTORY_YEARS (1.5 años)
# a propósito: 8 meses alcanza para una primera vuelta de backtesting y la
# descarga tarda bastante menos (pedido del usuario, sep 2026). Se puede
# ampliar después volviendo a correr el script si el backtest pide más
# historia para confiar en el resultado.
FOREX_HISTORY_MONTHS = 8
HISTORY_DAYS = FOREX_HISTORY_MONTHS * 30
THREADS = 20  # mismo default que trae la CLI de duka


def fetch_ticks_df(duka_symbol: str, start: date, end: date) -> pd.DataFrame:
    """Descarga tick a tick vía duka.app.app() (misma función que usa su
    CLI) a una carpeta temporal, y devuelve un DataFrame indexado por
    datetime UTC con columnas mid/volume ya calculadas."""
    tmp_dir = tempfile.mkdtemp(prefix="duka_")
    try:
        duka_fetch([duka_symbol], start, end, THREADS, TimeFrame.TICK, tmp_dir, True)
        files = [f for f in os.listdir(tmp_dir) if f.startswith(duka_symbol)]
        if not files:
            return pd.DataFrame()
        df = pd.read_csv(os.path.join(tmp_dir, files[0]))
        if df.empty:
            return df
        df["datetime"] = pd.to_datetime(df["time"]).dt.tz_localize("UTC")
        df["mid"] = (df["ask"] + df["bid"]) / 2
        df["volume"] = df["ask_volume"] + df["bid_volume"]
        return df.sort_values("datetime").set_index("datetime")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def ticks_to_ohlcv(df_ticks: pd.DataFrame, rule: str) -> pd.DataFrame:
    ohlc = df_ticks["mid"].resample(rule, label="left", closed="left").ohlc()
    vol = df_ticks["volume"].resample(rule, label="left", closed="left").sum()
    out = ohlc.join(vol.rename("volume")).dropna(subset=["open"]).reset_index()
    # Mismo formato de columnas que fetch_data.py: timestamp (ms), OHLCV, datetime.
    out["timestamp"] = out["datetime"].astype("int64") // 10**6
    return out[["timestamp", "open", "high", "low", "close", "volume", "datetime"]]


def main():
    os.makedirs(config.DATA_DIR, exist_ok=True)
    end = date.today() - timedelta(days=1)  # ayer: hoy puede estar incompleto
    start = end - timedelta(days=HISTORY_DAYS)

    for internal_symbol, duka_symbol in FOREX_SYMBOLS.items():
        print(f"\n=== {internal_symbol} ({duka_symbol}, desde {start} hasta {end}) ===")
        df_ticks = fetch_ticks_df(duka_symbol, start, end)
        if df_ticks.empty:
            print(f"  [!] Sin datos para {internal_symbol}, se salta.")
            continue
        fname = internal_symbol.replace("/", "_")
        for tf_label, rule in RESAMPLE_RULE.items():
            df_ohlcv = ticks_to_ohlcv(df_ticks, rule)
            path = os.path.join(config.DATA_DIR, f"{fname}_{tf_label}.csv")
            df_ohlcv.to_csv(path, index=False)
            print(f"  {tf_label}: {len(df_ohlcv)} velas guardadas en {path}")
            if len(df_ohlcv) > 0:
                print(f"    Rango: {df_ohlcv['datetime'].iloc[0]} -> {df_ohlcv['datetime'].iloc[-1]}")


if __name__ == "__main__":
    main()
