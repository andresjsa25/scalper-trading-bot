"""Criterio 2 (parte 1): una prueba por definicion de la seccion 3 (volumen, FVG, rechazo, estructura, barrida, Fibonacci) y pivotes."""
import os
import sys

import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from estudio_sinteticos import velas, zigzag, invertir, con_prefijo  # noqa: E402
from estudio_eventos.indicadores import pivotes_confirmados  # noqa: E402
from estudio_eventos.patrones import (  # noqa: E402
    volumen_alto, formacion_fvg, fvg_en, vela_rechazo, estructura_mayor_alineada,
    barrida_liquidez, zona_fibonacci)

# --- Fixtures a mano -------------------------------------------------------------------------

FVG_ALCISTA = [
    (100.0, 100.5, 99.5, 99.8),   # a: high = 100.5
    (99.8, 103.0, 99.7, 102.8),   # b: impulso
    (102.8, 104.0, 101.0, 103.5),  # c: low = 101.0 > 100.5 -> FVG zona (100.5, 101.0)
]
ARRIBA = (103.5, 104.5, 102.0, 103.0)     # no toca la zona
RELLENO = (103.0, 103.2, 100.8, 102.0)    # entra en la zona (100.5, 101.0)
TOCA = (102.0, 102.5, 100.9, 101.5)       # toca la zona sin estar rellena antes

PREV_BAJISTA = (101.0, 101.2, 99.8, 100.0)
PREV_ALCISTA = (99.0, 100.5, 98.5, 100.2)
MARTILLO = (100.0, 101.0, 96.0, 100.8)    # mecha inferior 4 >= 2 x cuerpo 0.8, cierre en mitad superior
ENVOLVENTE = (99.8, 101.8, 99.6, 101.5)   # abre < cierre previo (100.0), cierra > apertura previa (101.0)

# Barrida larga: pivote minimo confirmado en la vela 4 (low 90.0), confirmado en la vela 7
BARRIDA_BASE = [
    (100.0, 100.5, 99.5, 99.0), (99.0, 99.5, 97.5, 98.0), (98.0, 98.5, 96.5, 97.0),
    (97.0, 97.5, 95.5, 96.0), (96.0, 96.5, 90.0, 92.0), (92.0, 96.0, 91.5, 95.0),
    (95.0, 98.0, 94.5, 97.5), (97.5, 100.0, 97.0, 99.5),
]
BARRIDA = (99.5, 99.8, 89.0, 92.0)        # low 89 < 90 y cierre 92 > 90
SIN_BARRIDA = (99.5, 99.8, 89.0, 89.5)    # cierra debajo del pivote: ruptura, no barrida


def _fvg_con(*extra):
    return velas(list(FVG_ALCISTA) + list(extra))


class TestVolumenAlto:
    def test_umbral_1_5_veces_media_de_20_anteriores_sin_la_actual(self):
        # 20 velas de volumen 100 antes; en la vela 20 el volumen es 150 = 1,5 x 100 -> alto.
        vols = [100.0] * 20 + [150.0] + [100.0] * 3
        df = velas([(100, 101, 99, 100, v) for v in vols])
        assert bool(volumen_alto(df).iloc[20]) is True

    def test_por_debajo_del_umbral_no_es_alto(self):
        vols = [100.0] * 20 + [149.9] + [100.0] * 3
        df = velas([(100, 101, 99, 100, v) for v in vols])
        assert bool(volumen_alto(df).iloc[20]) is False


class TestFvg:
    def test_fvg_alcista_formacion_en_la_vela_3(self):
        df = _fvg_con()
        assert formacion_fvg(df, "long").tolist() == [False, False, True]

    def test_sin_hueco_no_hay_fvg_alcista(self):
        df = velas([FVG_ALCISTA[0], FVG_ALCISTA[1], (102.8, 104.0, 100.4, 103.5)])  # low 100.4 <= 100.5
        assert not formacion_fvg(df, "long").any()

    def test_fvg_alcista_zona_es_high_i_menos_2_hasta_low_i(self):
        df = _fvg_con(ARRIBA, TOCA)
        assert fvg_en(df, 4, "long") == (100.5, 101.0)

    def test_fvg_vigente_con_2_velas_de_antiguedad(self):
        df = _fvg_con(ARRIBA, TOCA)  # FVG en j=2, senal en i=4 (2 velas despues)
        assert fvg_en(df, 4, "long") is not None

    def test_fvg_no_vigente_con_30_velas_de_antiguedad(self):
        # Limite exacto de la ventana de 24 velas no se prueba: la ambiguedad se anota en el reporte.
        df = _fvg_con(*([ARRIBA] * 27 + [TOCA]))  # senal a 28 velas del FVG
        assert fvg_en(df, len(df) - 1, "long") is None

    def test_fvg_se_rellena_si_vela_posterior_entra_en_la_zona(self):
        df = _fvg_con(RELLENO, TOCA)  # RELLENO entra en la zona antes de la senal
        assert fvg_en(df, 4, "long") is None

    def test_relleno_que_toca_solo_el_borde_superior_no_rellena(self):
        borde = (102.0, 102.5, 101.0, 101.5)  # low = borde superior (101.0): no cruza el interior
        assert fvg_en(_fvg_con(borde, TOCA), 4, "long") == (100.5, 101.0)

    def test_relleno_que_entra_un_poco_en_la_zona_si_rellena(self):
        entra_poco = (102.0, 102.5, 100.95, 101.5)  # low 100.95 < 101.0 y high > 100.5: cruza el interior
        assert fvg_en(_fvg_con(entra_poco, TOCA), 4, "long") is None

    def test_fvg_solo_cuenta_como_tocado_si_la_vela_de_senal_entra(self):
        assert fvg_en(_fvg_con(ARRIBA), 3, "long") is None
        assert fvg_en(_fvg_con(TOCA), 3, "long") == (100.5, 101.0)

    def test_fvg_toque_solo_en_el_borde_no_cuenta(self):
        borde = (102.0, 102.5, 101.0, 101.5)  # low = borde superior de la zona (101.0): no entra
        assert fvg_en(_fvg_con(borde), 3, "long") is None

    def test_fvg_formado_en_la_propia_senal_es_vigente(self):
        # Decision de Andres: la ventana de 24 velas incluye la vela de senal i (j == i). Sin toque (H3).
        df = velas(list(FVG_ALCISTA))  # FVG formado en j=2 = i
        assert fvg_en(df, 2, "long", tocado=False) == (100.5, 101.0)

    def test_fvg_formado_a_23_velas_es_vigente_y_a_24_no(self):
        # i = 26. FVG en j=2 -> antiguedad 24 (i-24): no vigente. Con 23 velas de por medio (i=25): vigente.
        df_24 = _fvg_con(*([ARRIBA] * 24))
        assert fvg_en(df_24, 26, "long", tocado=False) is None
        df_23 = _fvg_con(*([ARRIBA] * 23))
        assert fvg_en(df_23, 25, "long", tocado=False) == (100.5, 101.0)

    def test_fvg_bajista_espejo_de_formacion_y_zona(self):
        df = invertir(_fvg_con(ARRIBA, TOCA))
        assert formacion_fvg(df, "short").tolist() == [False, False, True, False, False]
        zona = fvg_en(df, 4, "short")
        assert zona is not None
        assert zona[0] == pytest.approx(899.0) and zona[1] == pytest.approx(899.5)

    def test_fvg_bajista_relleno_invalida(self):
        df = invertir(_fvg_con(RELLENO, TOCA))
        assert fvg_en(df, 4, "short") is None


class TestVelaRechazo:
    def test_martillo_long_con_mecha_2x_y_cierre_arriba(self):
        df = velas([PREV_ALCISTA, MARTILLO])
        assert bool(vela_rechazo(df, "long").iloc[1]) is True

    def test_martillo_con_cierre_en_mitad_inferior_no_cuenta(self):
        # mecha inferior 9 >= 2 x cuerpo 4, pero cierra en 99 < punto medio 100
        df = velas([PREV_ALCISTA, (103.0, 110.0, 90.0, 99.0)])
        assert bool(vela_rechazo(df, "long").iloc[1]) is False

    def test_mecha_menor_a_2x_cuerpo_no_cuenta(self):
        df = velas([PREV_ALCISTA, (100.0, 101.0, 99.0, 100.8)])  # mecha 1 < 2 x 0.8
        assert bool(vela_rechazo(df, "long").iloc[1]) is False

    def test_envolvente_alcista_con_vela_previa_bajista(self):
        df = velas([PREV_BAJISTA, ENVOLVENTE])
        assert bool(vela_rechazo(df, "long").iloc[1]) is True

    def test_envolvente_alcista_no_cuenta_si_la_previa_es_alcista(self):
        df = velas([PREV_ALCISTA, ENVOLVENTE])
        assert bool(vela_rechazo(df, "long").iloc[1]) is False

    def test_rechazo_short_es_espejo_del_long(self):
        assert bool(vela_rechazo(invertir(velas([PREV_ALCISTA, MARTILLO])), "short").iloc[1]) is True
        assert bool(vela_rechazo(invertir(velas([PREV_BAJISTA, ENVOLVENTE])), "short").iloc[1]) is True


def _zigzag_mayor(l2, cierre_final=100.0):
    """4h: min 90 en 4, max 105 en 8, min l2 en 12, subida hasta 15."""
    filas = zigzag([(0, 100.0), (4, 90.0), (8, 105.0), (12, l2), (15, cierre_final)])
    return velas(filas, freq="4h")


class TestEstructuraMayor:
    def test_minimo_confirmado_mas_alto_que_el_anterior_alinea_long(self):
        mayor = _zigzag_mayor(l2=95.0)
        instante = mayor.index[15] + pd.Timedelta("4h")  # cierre de la vela 4h 15
        assert estructura_mayor_alineada(mayor, instante, "long", pd.Timedelta("4h")) is True

    def test_minimo_mas_bajo_no_alinea_long(self):
        mayor = _zigzag_mayor(l2=85.0)
        instante = mayor.index[15] + pd.Timedelta("4h")
        assert estructura_mayor_alineada(mayor, instante, "long", pd.Timedelta("4h")) is False

    def test_no_usa_velas_4h_no_cerradas_en_el_instante(self):
        # El pivote en 12 solo queda confirmado con la vela 15: al cierre de la 14 no existe.
        mayor = _zigzag_mayor(l2=95.0)
        instante = mayor.index[14] + pd.Timedelta("4h")
        assert estructura_mayor_alineada(mayor, instante, "long", pd.Timedelta("4h")) is False

    def test_espejo_short_con_maximos(self):
        mayor = invertir(_zigzag_mayor(l2=95.0))  # los minimos pasan a maximos mas bajos
        instante = mayor.index[15] + pd.Timedelta("4h")
        assert estructura_mayor_alineada(mayor, instante, "short", pd.Timedelta("4h")) is True


class TestBarridaLiquidez:
    def test_barrida_long_low_bajo_pivote_y_cierre_arriba(self):
        df = velas(BARRIDA_BASE + [BARRIDA])
        flags = barrida_liquidez(df, "long")
        assert bool(flags.iloc[8]) is True

    def test_cierre_debajo_del_pivote_no_es_barrida(self):
        df = velas(BARRIDA_BASE + [SIN_BARRIDA])
        assert bool(barrida_liquidez(df, "long").iloc[8]) is False

    def test_barrida_espejo_short(self):
        df = invertir(velas(BARRIDA_BASE + [BARRIDA]))
        assert bool(barrida_liquidez(df, "short").iloc[8]) is True

    def test_pivote_minimo_solo_existe_tras_3_velas(self):
        piv = pivotes_confirmados(velas(BARRIDA_BASE + [BARRIDA]), n=3)
        assert piv["pivot_min"].iloc[7] == pytest.approx(90.0)  # pivote en 4, confirmado en 4 + 3 = 7
        assert piv["pivot_min"].iloc[:7].isna().all()  # antes de la confirmacion no existe


class TestZonaFibonacci:
    # Tramo L (min 80 en 4) -> H (max 110 en 8); R = 30,4; zona [91,41 ; 95,0]. Barrida de 79,0 en la vela 12.
    ZIG = zigzag([(0, 100.0), (4, 80.0), (8, 110.0), (11, 93.0)])

    def test_cierre_dentro_de_la_zona_long(self):
        df = velas(self.ZIG + [(93.5, 94.0, 79.0, 93.0)])
        assert zona_fibonacci(df, 12, "long") is True

    def test_cierre_fuera_de_la_zona_long(self):
        df = velas(self.ZIG + [(93.5, 97.5, 79.0, 97.0)])
        assert zona_fibonacci(df, 12, "long") is False

    def test_espejo_short(self):
        df = invertir(velas(self.ZIG + [(93.5, 94.0, 79.0, 93.0)]))
        assert zona_fibonacci(df, 12, "short") is True

