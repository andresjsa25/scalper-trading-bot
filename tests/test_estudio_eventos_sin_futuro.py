"""Criterio 3: ningun indicador ni evento usa informacion posterior a la vela de senal.

Dos pruebas por cada funcion: (a) truncar el futuro (df.iloc[:i+1]) no cambia el valor en i;
(b) reemplazar las velas posteriores a i por otras no cambia el valor en i.
Sintetico siempre; sobre un prefijo real de data/ si el archivo existe.
"""
import os
import sys

import numpy as np
import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from estudio_sinteticos import aleatorio  # noqa: E402
from estudio_eventos.indicadores import rsi, adx, bollinger, atr, pivotes_confirmados  # noqa: E402
from estudio_eventos.patrones import (  # noqa: E402
    volumen_alto, formacion_fvg, fvg_en, vela_rechazo, barrida_liquidez, zona_fibonacci)
from estudio_eventos.hipotesis import h1, h2, h3, h4, h5  # noqa: E402

DATA = os.path.join(ROOT, "data", "backtest_snapshot")


def _iguales(a, b):
    """Igualdad que trata NaN == NaN y compara tuplas/None/bool."""
    if a is None or b is None:
        return a is None and b is None
    if isinstance(a, tuple):
        return isinstance(b, tuple) and len(a) == len(b) and all(_iguales(x, y) for x, y in zip(a, b))
    if isinstance(a, (float, np.floating)) and pd.isna(a):
        return pd.isna(b)
    if isinstance(a, pd.DataFrame):
        return a.equals(b) or (a.fillna(-1e18).values == b.fillna(-1e18).values).all()
    return a == b


# Cada entrada: (nombre, f(df, mayor) -> Serie/DataFrame/escalar en la ultima vela, o f(df, mayor, i) para puntos)
SERIES = [
    ("rsi", lambda d, m: rsi(d["close"])),
    ("adx", lambda d, m: adx(d)),
    ("bollinger_ancho", lambda d, m: bollinger(d["close"])["ancho"]),
    ("atr", lambda d, m: atr(d)),
    ("pivotes", lambda d, m: pivotes_confirmados(d)),
    ("volumen_alto", lambda d, m: volumen_alto(d)),
    ("formacion_fvg_long", lambda d, m: formacion_fvg(d, "long")),
    ("vela_rechazo_long", lambda d, m: vela_rechazo(d, "long")),
    ("barrida_long", lambda d, m: barrida_liquidez(d, "long")),
    ("h1_long", lambda d, m: h1(d, "long")),
    ("h1_con_estructura", lambda d, m: h1(d, "long", df_mayor=m)),
    ("h2_long", lambda d, m: h2(d, "long")),
    ("h3_long", lambda d, m: h3(d, "long")),
    ("h4_long", lambda d, m: h4(d, "long")),
    ("h5_long", lambda d, m: h5(d, "long")),
    ("h5_short", lambda d, m: h5(d, "short", volumen_barrida=True, fvg_ruptura=True)),
]
PUNTOS = [
    ("fvg_en_long", lambda d, m, i: fvg_en(d, i, "long")),
    ("zona_fibonacci_long", lambda d, m, i: zona_fibonacci(d, i, "long")),
]


def _ultimo(serie):
    return serie.iloc[-1]


def _en(serie, i):
    return serie.iloc[i]


def _verificar_truncado(df, mayor, posiciones):
    for nombre, f in SERIES:
        completa = f(df, mayor)
        for i in posiciones:
            parcial = f(df.iloc[: i + 1], mayor)
            if isinstance(completa, pd.DataFrame):
                ok = all(_iguales(completa.iloc[i][c], parcial.iloc[-1][c]) for c in completa.columns)
            else:
                ok = _iguales(_en(completa, i), _ultimo(parcial))
            assert ok, f"{nombre}: la senal en {i} cambia al truncar el futuro"
    for nombre, f in PUNTOS:
        for i in posiciones:
            assert _iguales(f(df, mayor, i), f(df.iloc[: i + 1], mayor, i)), f"{nombre}: cambia en {i} al truncar"


def _verificar_futuro_alterado(df, mayor, posiciones, semilla_alt=99):
    alt = aleatorio(len(df), semilla_alt, inicio=str(df.index[0]))
    for i in posiciones:
        df_alt = df.copy()
        df_alt.iloc[i + 1:] = alt.iloc[i + 1:].values
        for nombre, f in SERIES:
            a = f(df, mayor)
            b = f(df_alt, mayor)
            if isinstance(a, pd.DataFrame):
                ok = all(_iguales(a.iloc[i][c], b.iloc[i][c]) for c in a.columns)
            else:
                ok = _iguales(_en(a, i), _en(b, i))
            assert ok, f"{nombre}: la senal en {i} cambia si cambian velas posteriores"
        for nombre, f in PUNTOS:
            assert _iguales(f(df, mayor, i), f(df_alt, mayor, i)), f"{nombre}: cambia en {i} con futuro alterado"


class TestSintetico:
    def setup_method(self):
        self.df = aleatorio(400, semilla=3)
        self.mayor = aleatorio(120, semilla=4, freq="4h")

    def test_truncar_el_futuro_no_cambia_la_senal_en_i(self):
        _verificar_truncado(self.df, self.mayor, range(60, 400, 17))

    def test_velas_posteriores_no_cambian_la_senal_en_i(self):
        _verificar_futuro_alterado(self.df, self.mayor, [80, 150, 260, 340])


def _cargar(nombre, nrows):
    ruta = os.path.join(DATA, nombre)
    if not os.path.exists(ruta):
        return None
    d = pd.read_csv(ruta, nrows=nrows)
    d.index = pd.to_datetime(d["datetime"], utc=True)
    return d[["open", "high", "low", "close", "volume"]].astype(float)


class TestDatosReales:
    @pytest.mark.skipif(not os.path.exists(os.path.join(DATA, "BTC_USDT_USDT_1h.csv")),
                        reason="data/ no existe en este checkout (los datos no se suben al repo)")
    def test_prefijo_real_btc_1h_y_4h_no_cambia_senales(self):
        df = _cargar("BTC_USDT_USDT_1h.csv", 1200)
        mayor = _cargar("BTC_USDT_USDT_4h.csv", 320)
        _verificar_truncado(df, mayor, range(250, 1200, 61))
