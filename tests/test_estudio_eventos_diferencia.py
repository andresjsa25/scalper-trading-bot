"""Diferencia evento - referencia al azar (spec seccion 5 y anexo 2026-10-04).

Datos sinteticos con ATR conocido a mano: todas las velas tienen rango 2 (TR = 2, ATR = 2) salvo la vela de senal
de cada escenario, que tiene rango 16 (TR = 16 sobre cierre previo 100) y ATR = (13*2 + 16)/14 = 3.
Velas planas: open = close = 100. Entrada teorica = open[i+1] = 100.
Resultado esperado por evento (costo c, d = 14):
  long  : ret = (14 - 100c) / 3          (close[i+8] = 114)
  short : ret = (14 - 100c) / 3          (close[i+8] = 86, s = -1)
  candidatas planas: ret = -100c / 2 = -50c, media = -50c
  diferencia = (14 - 100c)/3 + 50c = (14 + 50c) / 3
"""
import os
import sys

import numpy as np
import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from estudio_eventos.diferencia import retorno_atr, diferencias  # noqa: E402
from estudio_eventos.muestreo import deduplicar  # noqa: E402

PLANA = (100.0, 101.0, 99.0, 100.0)  # rango 2
BUMP = (100.0, 108.0, 92.0, 100.0)  # rango 16: ATR de la vela de senal = 3


def _cierre8(sentido, d=14.0):
    if sentido == "long":
        return (100.0, 100.0 + d, 100.0, 100.0 + d)
    return (100.0, 100.0, 100.0 - d, 100.0 - d)


def _df(horas, filas, sentido):
    base = pd.Timestamp("2025-01-01", tz="UTC")
    idx = pd.DatetimeIndex([base + pd.Timedelta(days=k, hours=h) for k, h in enumerate(horas)])
    df = pd.DataFrame(filas, columns=["open", "high", "low", "close"], index=idx, dtype=float)
    df["volume"] = 100.0
    df["bloque"] = "E"
    df["sentido"] = sentido
    return df


def _escenario(n_pool, sentido, d=14.0):
    """14 velas de calentamiento (hora 3), n_pool candidatas (hora 10), evento en hora 10, 7 velas planas, cierre +8."""
    e = 14 + n_pool
    horas = [3] * 14 + [10] * (n_pool + 1) + [3] * 8
    filas = [PLANA] * 14 + [PLANA] * n_pool + [BUMP] + [PLANA] * 7 + [_cierre8(sentido, d)]
    return _df(horas, filas, sentido), e


def _ev(posiciones, sentido):
    return pd.DataFrame({"pos": posiciones, "sentido": sentido})


def _fila(res, pos):
    return res.loc[res["pos"] == pos].iloc[0]


def _diferencia(df, e, sentido, costo):
    return float(_fila(diferencias(df, _ev([e], sentido), costo, semilla=0), e)["diferencia"])


def test_calculo_espejo_long_short_con_costo_base_y_sensibilidad():
    for costo in (0.0008, 0.0011, 0.0014):
        df_l, e = _escenario(26, "long")
        df_s, _ = _escenario(26, "short")
        assert retorno_atr(df_l, e, "long", costo) == pytest.approx((14 - 100 * costo) / 3, abs=1e-12)
        assert retorno_atr(df_s, e, "short", costo) == pytest.approx((14 - 100 * costo) / 3, abs=1e-12)
        esperado = (14 + 50 * costo) / 3
        assert _diferencia(df_l, e, "long", costo) == pytest.approx(esperado, abs=1e-9)
        assert _diferencia(df_s, e, "short", costo) == pytest.approx(esperado, abs=1e-9)


def test_referencia_con_menos_de_20_candidatas_excluye_el_evento():
    df19, e19 = _escenario(19, "long")
    res = diferencias(df19, _ev([e19], "long"), 0.0011, semilla=0)
    fila = _fila(res, e19)
    assert bool(fila["excluido"]) is True
    assert pd.isna(fila["diferencia"])
    assert isinstance(fila["motivo"], str) and fila["motivo"] != ""
    assert int(res["excluido"].sum()) == 1
    assert int(res["diferencia"].notna().sum()) == 0

    # Control: con 20 candidatas el mismo evento si tiene diferencia.
    df20, e20 = _escenario(20, "long")
    res20 = diferencias(df20, _ev([e20], "long"), 0.0011, semilla=0)
    assert bool(_fila(res20, e20)["excluido"]) is False
    assert _fila(res20, e20)["diferencia"] == pytest.approx((14 + 50 * 0.0011) / 3, abs=1e-9)


def test_evento_sin_vela_mas_8_se_excluye_y_se_cuenta():
    # Evento en hora 10 con solo 4 velas posteriores: no hay cierre a +8.
    horas = [3] * 14 + [10] * 21 + [3] * 3
    filas = [PLANA] * 14 + [PLANA] * 20 + [BUMP] + [PLANA] * 3
    df = _df(horas, filas, "long")
    res = diferencias(df, _ev([34], "long"), 0.0011, semilla=0)
    fila = _fila(res, 34)
    assert bool(fila["excluido"]) is True
    assert pd.isna(fila["diferencia"])
    assert int(res["excluido"].sum()) == 1


def test_candidata_sin_vela_mas_8_no_entra_en_la_referencia():
    # 20 candidatas validas (filas 14..33) y una candidata en la fila 37 sin vela +8.
    # Si la fila 37 entrara en la referencia, la media dejaria de ser -50c (o daria NaN).
    horas = [3] * 14 + [10] * 20 + [10] + [3, 3, 10, 3, 3, 3, 3, 3]
    filas = [PLANA] * 14 + [PLANA] * 20 + [BUMP] + [PLANA] * 7 + [_cierre8("long")]
    df = _df(horas, filas, "long")
    assert len(horas) == len(filas) == 43
    res = diferencias(df, _ev([34], "long"), 0.0011, semilla=0)
    assert _fila(res, 34)["diferencia"] == pytest.approx((14 + 50 * 0.0011) / 3, abs=1e-9)


def test_eventos_suprimidos_por_dedup_no_entran_al_resultado():
    # Eventos en 34, 37 (a 3 velas de 34: suprimido) y 42 (a 8 velas de 34: cuenta).
    horas = [3] * 14 + [10] * 20 + [10] + [3, 3] + [10] + [3] * 4 + [10] + [3] * 8
    filas = [PLANA] * 50 + [_cierre8("long")]
    df = _df(horas, filas, "long")
    assert len(horas) == len(filas) == 51
    originales = pd.DataFrame({"simbolo": "BTC", "tf": "1h", "sentido": "long", "pos": [34, 37, 42]})
    contados = deduplicar(originales, ventana=8)
    assert contados["pos"].tolist() == [34, 42]
    res = diferencias(df, contados, 0.0011, semilla=0)
    assert sorted(res["pos"].tolist()) == [34, 42]
    assert 37 not in res["pos"].tolist()
    assert int((~res["excluido"].astype(bool)).sum()) == 2


def test_mismo_seed_da_resultado_identico():
    rng = np.random.default_rng(123)
    n = 80
    horas = [10 if k % 2 == 0 else 3 for k in range(n)]
    o = 100 + rng.normal(0, 1, n)
    c = o + rng.normal(0, 1, n)
    h = np.maximum(o, c) + np.abs(rng.normal(0, 0.5, n))
    l = np.minimum(o, c) - np.abs(rng.normal(0, 0.5, n))
    filas = list(zip(o, h, l, c))
    df = _df(horas, filas, "long")
    eventos = _ev([40, 60], "long")
    r1 = diferencias(df, eventos, 0.0011, semilla=7)
    r2 = diferencias(df, eventos, 0.0011, semilla=7)
    pd.testing.assert_frame_equal(r1, r2)
    assert len(r1) == 2
    assert r1["diferencia"].notna().all()
