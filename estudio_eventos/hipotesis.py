"""Hipotesis H1-H5 y sus versiones (seccion 3 de la spec). Devuelven una Serie bool en la vela de senal."""
import numpy as np
import pandas as pd

from estudio_eventos.indicadores import rsi, adx, bollinger, pivotes_confirmados
from estudio_eventos.patrones import (
    volumen_alto, formacion_fvg, fvg_en, vela_rechazo, estructura_mayor_alineada,
    barrida_liquidez, zona_fibonacci)


def _vacia(df):
    return pd.Series(False, index=df.index)


def h1(df: pd.DataFrame, direccion: str, rechazo: bool = True, fvg: bool = True,
       df_mayor: pd.DataFrame | None = None, duracion_senal: str = "1h", duracion_mayor: str = "4h") -> pd.Series:
    """RSI<30 + FVG vigente/sin rellenar/tocado + vela de rechazo. Con df_mayor: filtro de estructura mayor alineada."""
    rs = rsi(df["close"])
    base = (rs < 30) if direccion == "long" else (rs > 70)
    if rechazo:
        base = base & vela_rechazo(df, direccion)
    out = _vacia(df)
    for i in np.flatnonzero(base.to_numpy()):
        if fvg and fvg_en(df, i, direccion) is None:
            continue
        if df_mayor is not None and not estructura_mayor_alineada(
                df_mayor, df.index[i] + pd.Timedelta(duracion_senal), direccion, pd.Timedelta(duracion_mayor)):
            continue
        out.iloc[i] = True
    return out


def h2(df: pd.DataFrame, direccion: str, adx_filtro: bool = True, volumen: bool = True, fvg: bool = True) -> pd.Series:
    """ADX<20 + low<=banda inferior con cierre por encima + FVG vigente/sin rellenar/tocado + volumen alto."""
    banda = bollinger(df["close"])
    if direccion == "long":
        base = (df["low"] <= banda["inferior"]) & (df["close"] > banda["inferior"])
    else:
        base = (df["high"] >= banda["superior"]) & (df["close"] < banda["superior"])
    if adx_filtro:
        base = base & (adx(df) < 20)
    if volumen:
        base = base & volumen_alto(df)
    out = _vacia(df)
    for i in np.flatnonzero(base.to_numpy()):
        if fvg and fvg_en(df, i, direccion) is None:
            continue
        out.iloc[i] = True
    return out


def h3(df: pd.DataFrame, direccion: str, volumen: bool = True, fibonacci: bool = True, fvg: bool = True) -> pd.Series:
    """Barrida de liquidez + volumen alto + cierre en zona de Fibonacci + FVG vigente y sin rellenar."""
    base = barrida_liquidez(df, direccion)
    if volumen:
        base = base & volumen_alto(df)
    out = _vacia(df)
    for i in np.flatnonzero(base.to_numpy()):
        if fibonacci and not zona_fibonacci(df, i, direccion):
            continue
        if fvg and fvg_en(df, i, direccion, tocado=False) is None:
            continue
        out.iloc[i] = True
    return out


def _racha(booleanos: np.ndarray) -> np.ndarray:
    """Largo de la racha de True que termina en cada posicion."""
    racha = np.zeros(len(booleanos), dtype=int)
    for k, v in enumerate(booleanos):
        racha[k] = (racha[k - 1] + 1 if k > 0 else 1) if v else 0
    return racha


def h4(df: pd.DataFrame, direccion: str, volumen: bool = True, duracion_minima: int = 6) -> pd.Series:
    """Compresion (ancho Bollinger percentil <=20 de 100 velas, >= duracion_minima velas seguidas) + cierre fuera del maximo/minimo de la compresion.

    Percentil sobre hasta 100 anchos (incluido el actual), con al menos 20 validos. La compresion es la racha que
    termina en S-1; la senal en S exige cierre fuera del rango (high/low) de esas velas y volumen alto si corresponde.
    """
    ancho = bollinger(df["close"])["ancho"]
    p20 = ancho.rolling(100, min_periods=20).quantile(0.2, interpolation="linear")
    comprimido = (ancho <= p20).to_numpy()
    racha = _racha(comprimido)
    vol = volumen_alto(df).to_numpy()
    alto, bajo, cierre = df["high"].to_numpy(), df["low"].to_numpy(), df["close"].to_numpy()
    out = _vacia(df)
    for s in range(1, len(df)):
        r = racha[s - 1]
        if r < duracion_minima:
            continue
        if volumen and not vol[s]:
            continue
        if direccion == "long":
            if cierre[s] > alto[s - r:s].max():
                out.iloc[s] = True
        elif cierre[s] < bajo[s - r:s].min():
            out.iloc[s] = True
    return out


def h5(df: pd.DataFrame, direccion: str, volumen_barrida: bool = False, fvg_ruptura: bool = False) -> pd.Series:
    """Barrida en S; senal = primera vela en S+1..S+12 que cierra sobre el ultimo maximo confirmado antes de S, sin low menor al de S."""
    piv = pivotes_confirmados(df)
    barridas = barrida_liquidez(df, direccion).to_numpy()
    vol = volumen_alto(df).to_numpy()
    alto, bajo, cierre = df["high"].to_numpy(), df["low"].to_numpy(), df["close"].to_numpy()
    if direccion == "long":
        ref = piv["pivot_max"].ffill().shift(1).to_numpy()
        fvg = formacion_fvg(df, "long").to_numpy()
    else:
        ref = piv["pivot_min"].ffill().shift(1).to_numpy()
        fvg = formacion_fvg(df, "short").to_numpy()
    out = _vacia(df)
    for s in np.flatnonzero(barridas):
        if volumen_barrida and not vol[s]:
            continue
        if np.isnan(ref[s]):
            continue
        for j in range(s + 1, min(s + 12, len(df) - 1) + 1):
            if (direccion == "long" and bajo[j] < bajo[s]) or (direccion == "short" and alto[j] > alto[s]):
                break
            if (direccion == "long" and cierre[j] > ref[s]) or (direccion == "short" and cierre[j] < ref[s]):
                if not fvg_ruptura or fvg[s + 1: j + 1].any():
                    out.iloc[j] = True
                break
    return out
