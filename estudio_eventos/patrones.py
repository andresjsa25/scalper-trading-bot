"""Definiciones de la seccion 3 de la spec. direccion: 'long' o 'short' (espejo)."""
import numpy as np
import pandas as pd

from estudio_eventos.indicadores import pivotes_confirmados


def volumen_alto(df: pd.DataFrame, factor: float = 1.5, n: int = 20) -> pd.Series:
    """True si volume >= factor * media de los n volumenes anteriores (sin contar la vela actual)."""
    media_prev = df["volume"].shift(1).rolling(n).mean()
    return (df["volume"] >= factor * media_prev).astype(bool)


def formacion_fvg(df: pd.DataFrame, direccion: str) -> pd.Series:
    """True en la vela j de un FVG formado (alcista: low[j] > high[j-2]; bajista: high[j] < low[j-2])."""
    if direccion == "long":
        return (df["low"] > df["high"].shift(2)).astype(bool)
    return (df["high"] < df["low"].shift(2)).astype(bool)


def _solapa(alto, bajo, zona):
    return bajo <= zona[1] and alto >= zona[0]


def fvg_en(df: pd.DataFrame, i: int, direccion: str, ventana: int = 24, tocado: bool = True):
    """Zona (bajo, alto) del FVG vigente en i (formado en la ventana), sin rellenar por velas previas a i y tocado por la vela i; None si no hay.

    Vigente: formado en las 23 velas previas a i (j en [i-23, i-1]), ventana de 24 velas que incluye la de senal.
    Sin rellenar: ninguna vela j+1..i-1 se solapa con la zona. Si hay varios, devuelve el mas reciente valido.
    """
    alto = df["high"].to_numpy(dtype=float)
    bajo = df["low"].to_numpy(dtype=float)
    for j in range(i - 1, i - ventana, -1):
        if j < 2:
            break
        if direccion == "long":
            if not bajo[j] > alto[j - 2]:
                continue
            zona = (alto[j - 2], bajo[j])
        else:
            if not alto[j] < bajo[j - 2]:
                continue
            zona = (alto[j], bajo[j - 2])
        if any(_solapa(alto[k], bajo[k], zona) for k in range(j + 1, i)):
            continue
        if tocado and not _solapa(alto[i], bajo[i], zona):
            continue
        return zona
    return None


def vela_rechazo(df: pd.DataFrame, direccion: str) -> pd.Series:
    """Martillo (mecha >= 2x cuerpo, cierre en mitad superior) o envolvente alcista (espejo para short)."""
    o, h, l, c = df["open"], df["high"], df["low"], df["close"]
    cuerpo = (c - o).abs()
    medio = (h + l) / 2
    o_prev, c_prev = o.shift(1), c.shift(1)
    if direccion == "long":
        martillo = (cuerpo > 0) & (np.minimum(o, c) - l >= 2 * cuerpo) & (c > medio)
        envolvente = (c_prev < o_prev) & (o < c_prev) & (c > o_prev)
    else:
        martillo = (cuerpo > 0) & (h - np.maximum(o, c) >= 2 * cuerpo) & (c < medio)
        envolvente = (c_prev > o_prev) & (o > c_prev) & (c < o_prev)
    return (martillo | envolvente).astype(bool)


def _pivotes(serie: pd.Series, n: int) -> list:
    """(posicion del centro, precio) de cada pivote confirmado, en orden temporal."""
    valores = serie.to_numpy(dtype=float)
    return [(int(k) - n, float(valores[k])) for k in np.flatnonzero(~np.isnan(valores))]


def estructura_mayor_alineada(df_mayor: pd.DataFrame, instante: pd.Timestamp, direccion: str,
                              duracion: pd.Timedelta, n: int = 3) -> bool:
    """Usa solo velas de df_mayor cerradas en 'instante'; True si el ultimo minimo (max en short) confirmado es mas alto (bajo) que el anterior."""
    cerradas = df_mayor.loc[df_mayor.index <= instante - duracion]
    piv = pivotes_confirmados(cerradas, n)
    if direccion == "long":
        pivotes = _pivotes(piv["pivot_min"], n)
        return len(pivotes) >= 2 and pivotes[-1][1] > pivotes[-2][1]
    pivotes = _pivotes(piv["pivot_max"], n)
    return len(pivotes) >= 2 and pivotes[-1][1] < pivotes[-2][1]


def barrida_liquidez(df: pd.DataFrame, direccion: str, n: int = 3) -> pd.Series:
    """True si la vela hace low por debajo (high por encima) del ultimo pivote confirmado y cierra por encima (debajo)."""
    piv = pivotes_confirmados(df, n)
    if direccion == "long":
        ref = piv["pivot_min"].ffill()
        return ((df["low"] < ref) & (df["close"] > ref)).astype(bool)
    ref = piv["pivot_max"].ffill()
    return ((df["high"] > ref) & (df["close"] < ref)).astype(bool)


def zona_fibonacci(df: pd.DataFrame, i: int, direccion: str, n: int = 3) -> bool:
    """True si el cierre de la vela i cae en [H-0.618R, H-0.5R] del ultimo tramo confirmado L->H (R=H-L). Espejo para short."""
    piv = pivotes_confirmados(df.iloc[: i + 1], n)
    if direccion == "long":
        mins = _pivotes(piv["pivot_min"], n)
        if not mins:
            return False
        c_l, low_l = mins[-1]
        maxs = [p for p in _pivotes(piv["pivot_max"], n) if p[0] > c_l]
        if not maxs:
            return False
        alto_h = maxs[-1][1]
        r = alto_h - low_l
        if r <= 0:
            return False
        lo, hi = alto_h - 0.618 * r, alto_h - 0.5 * r
    else:
        maxs = _pivotes(piv["pivot_max"], n)
        if not maxs:
            return False
        c_h, alto_h = maxs[-1]
        mins = [p for p in _pivotes(piv["pivot_min"], n) if p[0] > c_h]
        if not mins:
            return False
        low_l = mins[-1][1]
        r = alto_h - low_l
        if r <= 0:
            return False
        lo, hi = low_l + 0.5 * r, low_l + 0.618 * r
    return bool(lo <= df["close"].iloc[i] <= hi)
