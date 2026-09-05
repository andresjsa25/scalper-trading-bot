"""
Volumen relativo -- proxy estándar de "agresión"/"órdenes grandes" para la
estrategia V6 (ver strategy_v6_orderflow_proxy.py). El video de origen usa
order flow real (tamaño de órdenes individuales, footprint) que no existe
en el histórico de velas de BingX -- esto NO es lo mismo, es la aproximación
más honesta disponible con los datos que hay: una vela con volumen muy por
encima de su propio promedio reciente es la señal más cercana a "hubo
actividad/agresión inusual en esta vela" que se puede sacar de OHLCV.
"""
import pandas as pd


def add_relative_volume(df: pd.DataFrame, period: int = 20, col_name: str = "rel_volume") -> pd.DataFrame:
    df = df.copy()
    avg_volume = df["volume"].rolling(window=period, min_periods=period).mean()
    df[col_name] = df["volume"] / avg_volume
    return df
