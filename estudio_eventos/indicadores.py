"""Indicadores y pivotes confirmados (solo usan velas hasta la posición actual)."""
import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view


def _tr(df: pd.DataFrame) -> pd.Series:
    cierre_prev = df["close"].shift(1)
    return pd.concat([df["high"] - df["low"], (df["high"] - cierre_prev).abs(),
                      (df["low"] - cierre_prev).abs()], axis=1).max(axis=1)


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    """RSI de Wilder."""
    delta = close.diff()
    ganancia = delta.clip(lower=0).fillna(0.0)
    perdida = (-delta.clip(upper=0)).fillna(0.0)
    ag = ganancia.ewm(alpha=1.0 / n, adjust=False).mean()
    ap = perdida.ewm(alpha=1.0 / n, adjust=False).mean()
    rs = ag / ap.where(ap > 0)
    valor = 100 - 100 / (1 + rs)
    valor = valor.where(ap > 0, np.where(ag > 0, 100.0, 50.0))
    valor.iloc[:n] = np.nan
    return valor


def adx(df: pd.DataFrame, n: int = 14) -> pd.Series:
    """ADX de Wilder."""
    sube = df["high"].diff()
    baja = -df["low"].diff()
    mas = pd.Series(np.where((sube > baja) & (sube > 0), sube, 0.0), index=df.index)
    menos = pd.Series(np.where((baja > sube) & (baja > 0), baja, 0.0), index=df.index)
    tr_s = _tr(df).ewm(alpha=1.0 / n, adjust=False).mean()
    di_mas = 100 * mas.ewm(alpha=1.0 / n, adjust=False).mean() / tr_s
    di_menos = 100 * menos.ewm(alpha=1.0 / n, adjust=False).mean() / tr_s
    dx = (100 * (di_mas - di_menos).abs() / (di_mas + di_menos).where(lambda s: s > 0)).fillna(0.0)
    valor = dx.ewm(alpha=1.0 / n, adjust=False).mean()
    valor.iloc[:n] = np.nan
    return valor


def bollinger(close: pd.Series, n: int = 20, k: float = 2.0) -> pd.DataFrame:
    """Bandas de Bollinger sobre SMA. Columnas: media, superior, inferior, ancho ((sup-inf)/media)."""
    ventanas = sliding_window_view(close.to_numpy(dtype=float), n)
    media = np.concatenate([np.full(n - 1, np.nan), ventanas.mean(axis=1)])
    desvio = np.concatenate([np.full(n - 1, np.nan), ventanas.std(axis=1)])  # ddof=0, como en la plataforma
    sup = media + k * desvio
    inf = media - k * desvio
    return pd.DataFrame({"media": media, "superior": sup, "inferior": inf, "ancho": (sup - inf) / media},
                        index=close.index)


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    """ATR de Wilder."""
    valor = _tr(df).ewm(alpha=1.0 / n, adjust=False).mean()
    valor.iloc[:n] = np.nan
    return valor


def pivotes_confirmados(df: pd.DataFrame, n: int = 3) -> pd.DataFrame:
    """Pivotes con n velas a cada lado. Columnas pivot_max y pivot_min: el precio del pivote en la fila j+n (cuando queda confirmado), NaN en el resto."""
    alto = df["high"].to_numpy(dtype=float)
    bajo = df["low"].to_numpy(dtype=float)
    pmax = np.full(len(df), np.nan)
    pmin = np.full(len(df), np.nan)
    if len(df) >= 2 * n + 1:
        vh = sliding_window_view(alto, 2 * n + 1)
        vl = sliding_window_view(bajo, 2 * n + 1)
        # Empates no son pivote: el centro debe ser estrictamente mayor (menor) que todas las demás velas de la ventana.
        es_max = vh[:, n] > np.delete(vh, n, axis=1).max(axis=1)
        es_min = vl[:, n] < np.delete(vl, n, axis=1).min(axis=1)
        # La ventana que empieza en s tiene su centro en s+n y queda confirmada en la fila s+2n.
        pmax[2 * n:] = np.where(es_max, vh[:, n], np.nan)
        pmin[2 * n:] = np.where(es_min, vl[:, n], np.nan)
    return pd.DataFrame({"pivot_max": pmax, "pivot_min": pmin}, index=df.index)
