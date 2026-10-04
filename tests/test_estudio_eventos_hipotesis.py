"""Criterio 2 (parte 2): H1-H5 y sus versiones (seccion 3), con series sinteticas construidas a mano.

Cada version se prueba con una serie donde solo falla la condicion que la version quita:
la hipotesis completa da False y la version da True.
"""
import os
import sys

import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from estudio_sinteticos import velas, zigzag, tendencia, con_prefijo  # noqa: E402
from estudio_eventos.hipotesis import h1, h2, h3, h4, h5  # noqa: E402


def _senal(serie):
    """Valor booleano en la ultima vela (la vela de senal de cada fixture)."""
    return bool(serie.iloc[-1])


# ---------------------------------------------------------------- H1
def _h1_filas(paso=-1.0, sin_hueco=False, senal_bajista=False):
    """Caida de 60 velas + FVG alcista (a, b, c) + vela d que no rellena + senal envolvente que toca la zona."""
    base = tendencia(60, 200.0, paso)
    P = 200.0 + 60 * paso  # cierre de la ultima vela de base
    c_low = 0.1 if sin_hueco else 0.8  # 0,1 < high(a) = 0,2 -> sin hueco
    tramo = [
        (P, P + 0.2, P - 1.0, P - 0.8),          # a
        (P - 0.8, P + 1.5, P - 0.9, P + 1.0),    # b impulso
        (P + 1.0, P + 1.5, P + c_low, P + 1.2),  # c: low P+0.8 -> zona (P+0.2, P+0.8)
        (P + 1.2, P + 1.3, P + 1.0, P + 1.1),    # d bajista, no entra en la zona
    ]
    if senal_bajista:
        tramo.append((P + 0.9, P + 1.0, P + 0.4, P + 0.5))  # toca la zona pero no es rechazo
    else:
        tramo.append((P + 0.5, P + 1.6, P + 0.4, P + 1.5))  # envolvente alcista que toca la zona
    return base + tramo


class TestH1:
    def test_completa_long_con_sobreventa_fvg_y_rechazo(self):
        assert _senal(h1(velas(_h1_filas()), "long")) is True

    def test_no_dispara_sin_sobreventa(self):
        # Mismo tramo final sobre una subida: RSI alto, el resto de condiciones se cumple.
        assert _senal(h1(velas(_h1_filas(paso=1.0)), "long")) is False

    def test_version_sin_fvg(self):
        df = velas(_h1_filas(sin_hueco=True))
        assert _senal(h1(df, "long")) is False
        assert _senal(h1(df, "long", fvg=False)) is True

    def test_version_sin_rechazo(self):
        df = velas(_h1_filas(senal_bajista=True))
        assert _senal(h1(df, "long")) is False
        assert _senal(h1(df, "long", rechazo=False)) is True

    def test_version_con_estructura_mayor_alineada(self):
        df = velas(_h1_filas())
        alineada = velas(zigzag([(0, 100.0), (4, 90.0), (8, 105.0), (12, 95.0), (15, 100.0)]), freq="4h")
        no_alineada = velas(zigzag([(0, 100.0), (4, 90.0), (8, 105.0), (12, 85.0), (15, 100.0)]), freq="4h")
        assert _senal(h1(df, "long", df_mayor=alineada)) is True
        assert _senal(h1(df, "long", df_mayor=no_alineada)) is False


# ---------------------------------------------------------------- H2
def _lateral(n=40):
    """Rango lateral alternado entre 100,0 y 100,5 con mechas distintas (ADX bajo)."""
    filas, previo = [], 100.0
    for k in range(n):
        c = 100.0 if k % 2 == 0 else 100.5
        o = previo
        filas.append((o, max(o, c) + (0.2 if k % 2 == 0 else 0.4), min(o, c) - (0.4 if k % 2 == 0 else 0.2), c))
        previo = c
    return filas


def _h2_filas(volumen_senal=300.0, sin_hueco=False, tendencia_previa=False, bajo_senal=2.0):
    """Lateral + dip (a) + impulso (b) + FVG (a, b, c) + vela d + senal que toca la zona bajo la banda inferior."""
    base = _lateral()
    P = base[-1][3]
    if tendencia_previa:
        base += tendencia(25, P, 0.8)
        P = base[-1][3]
    c_low = -0.45 if sin_hueco else -0.2
    tramo = [
        (P - 0.5, P - 0.4, P - 1.7, P - 1.5),             # a (dip)
        (P - 1.5, P - 0.6, P - 1.6, P - 0.7),             # b
        (P - 0.7, P + 0.0, P + c_low, P - 0.1),           # c: low P-0.2 > high(a) = P-0.4
        (P - 0.1, P + 0.1, P - 0.15, P - 0.12),           # d: no entra en la zona
        (P - 0.3, P - 0.25, P - bajo_senal, P - 0.35),    # senal: toca la zona y perfora la banda
    ]
    return base + tramo, volumen_senal


def _h2_df(**kw):
    filas, vol = _h2_filas(**kw)
    filas[-1] = filas[-1][:4] + (vol,)
    return velas(filas)


class TestH2:
    def test_completa_long(self):
        assert _senal(h2(_h2_df(), "long")) is True

    def test_version_sin_volumen(self):
        df = _h2_df(volumen_senal=100.0)
        assert _senal(h2(df, "long")) is False
        assert _senal(h2(df, "long", volumen=False)) is True

    def test_version_sin_fvg(self):
        df = _h2_df(sin_hueco=True)
        assert _senal(h2(df, "long")) is False
        assert _senal(h2(df, "long", fvg=False)) is True

    def test_version_sin_adx(self):
        # Tendencia previa: ADX alto (no lateral), resto de condiciones iguales.
        df = _h2_df(tendencia_previa=True, bajo_senal=20.0)
        assert _senal(h2(df, "long")) is False
        assert _senal(h2(df, "long", adx_filtro=False)) is True


# ---------------------------------------------------------------- H3
def _h3_df(volumen_senal=300.0, cierre_senal=93.0):
    """Tramo L (min 80 en 4) -> H (max 110 en 8) -> caida a 93; FVG en el tramo alcista; barrida a 79 cerrando en 93."""
    zig = zigzag([(0, 100.0), (4, 80.0), (8, 110.0), (11, 93.0)])
    barrida = (93.5, max(93.5, cierre_senal) + 0.5, 79.0, cierre_senal, volumen_senal)
    return velas(con_prefijo(zig + [barrida], precio=100.0))


class TestH3:
    def test_completa_long(self):
        assert _senal(h3(_h3_df(), "long")) is True

    def test_version_sin_volumen(self):
        df = _h3_df(volumen_senal=100.0)
        assert _senal(h3(df, "long")) is False
        assert _senal(h3(df, "long", volumen=False)) is True

    def test_version_sin_fibonacci(self):
        df = _h3_df(cierre_senal=97.0)  # cierra fuera de [91,41 ; 95,0]
        assert _senal(h3(df, "long")) is False
        assert _senal(h3(df, "long", fibonacci=False)) is True


# ---------------------------------------------------------------- H4
def _h4_df(k=6, cierre_senal=100.5, volumen_senal=300.0):
    """60 velas planas, 20 de oscilacion amplia (ancho Bollinger alto), 19+k planas (compresion) y la ruptura.

    La compresion que termina en S-1 tiene exactamente k velas (las anteriores tienen ancho alto).
    """
    filas = [(100.0, 100.0, 100.0, 100.0)] * 60
    previo = 100.0
    for idx in range(20):
        c = 97.0 if idx % 2 == 0 else 103.0
        filas.append((previo, max(previo, c) + 0.5, min(previo, c) - 0.5, c))
        previo = c
    filas += [(100.0, 100.0, 100.0, 100.0)] * (19 + k)
    filas.append((100.0, cierre_senal + 0.1, 99.9, cierre_senal, volumen_senal))
    return velas(filas)


class TestH4:
    def test_completa_long_compresion_de_6_y_ruptura_sobre_el_maximo(self):
        assert _senal(h4(_h4_df(k=6), "long")) is True

    def test_compresion_de_5_velas_no_alcanza(self):
        assert _senal(h4(_h4_df(k=5), "long")) is False

    def test_ruptura_que_no_supera_el_maximo_no_cuenta(self):
        assert _senal(h4(_h4_df(k=6, cierre_senal=99.9), "long")) is False

    def test_version_sin_volumen(self):
        df = _h4_df(k=6, volumen_senal=100.0)
        assert _senal(h4(df, "long")) is False
        assert _senal(h4(df, "long", volumen=False)) is True

    def test_version_compresion_de_1_vela(self):
        df = _h4_df(k=1)
        assert _senal(h4(df, "long")) is False
        assert _senal(h4(df, "long", duracion_minima=1)) is True


# ---------------------------------------------------------------- H5
def _h5_df(r=13, volumen_s=300.0, lo_relleno=90.5, lo_ruptura=99.0):
    """Max 105,2 (vela 3) -> min 89,8 (vela 7, confirmada en 10) -> barrida S (vela 11, low 88, cierre 91).

    Relleno (vela 12..r-1) sin romper nada; ruptura R en la vela r cierra en 106.
    Devuelve (df, posicion de R).
    """
    prefijo = [(100.0, 100.0, 100.0, 100.0)] * 25
    zig = zigzag([(0, 100.0), (3, 105.0), (7, 90.0), (10, 95.0)])  # velas 0..10
    S = (99.5, 99.8, 88.0, 91.0, volumen_s)                         # vela 11
    filas = prefijo + zig + [S]
    for _ in range(12, r):
        filas.append((91.0, 100.0, lo_relleno, 98.0))
    filas.append((101.0, 106.5, lo_ruptura, 106.0))                 # vela r
    return velas(filas), len(filas) - 1


class TestH5:
    def test_base_barrida_y_ruptura_dentro_de_12_velas(self):
        df, i = _h5_df(r=13)
        assert bool(h5(df, "long").iloc[i]) is True

    def test_ruptura_en_s_mas_12_cuenta(self):
        df, i = _h5_df(r=23)
        assert bool(h5(df, "long").iloc[i]) is True

    def test_ruptura_en_s_mas_13_no_cuenta(self):
        df, i = _h5_df(r=24)
        assert bool(h5(df, "long").iloc[i]) is False

    def test_relleno_con_low_menor_al_de_la_barrida_invalida(self):
        df, i = _h5_df(r=13, lo_relleno=87.0)
        assert bool(h5(df, "long").iloc[i]) is False

    def test_version_base_mas_volumen_en_la_barrida(self):
        df_bajo, i = _h5_df(volumen_s=100.0)
        df_alto, j = _h5_df(volumen_s=300.0)
        assert bool(h5(df_bajo, "long").iloc[i]) is True
        assert bool(h5(df_bajo, "long", volumen_barrida=True).iloc[i]) is False
        assert bool(h5(df_alto, "long", volumen_barrida=True).iloc[j]) is True

    def test_version_base_mas_fvg_alcista_formado_en_la_ruptura(self):
        df_sin, i = _h5_df(lo_ruptura=99.0)    # low R <= high(S) = 99,8: sin hueco
        df_con, j = _h5_df(lo_ruptura=100.5)   # low R > 99,8: hueco alcista formado en la ruptura
        assert bool(h5(df_sin, "long", fvg_ruptura=True).iloc[i]) is False
        assert bool(h5(df_con, "long", fvg_ruptura=True).iloc[j]) is True

    def test_version_base_mas_ambos(self):
        df, i = _h5_df(volumen_s=300.0, lo_ruptura=100.5)
        assert bool(h5(df, "long", volumen_barrida=True, fvg_ruptura=True).iloc[i]) is True
        df_solo_vol, j = _h5_df(volumen_s=300.0, lo_ruptura=99.0)
        assert bool(h5(df_solo_vol, "long", volumen_barrida=True, fvg_ruptura=True).iloc[j]) is False
