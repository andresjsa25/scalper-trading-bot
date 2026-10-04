"""Resumen agregado por celda sin simbolo, excluidos por motivo, maximos en ATR y detalle por simbolo (spec seccion 5, 7 y anexo)."""
import os
import sys

import numpy as np
import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from estudio_sinteticos import velas  # noqa: E402
from estudio_eventos.fase0 import celdas_declaradas  # noqa: E402
from estudio_eventos.diferencia import maximos_atr, resumen_agregado, resumen_por_simbolo  # noqa: E402


def fila(simbolo="BTC", tf="1h", sentido="long", hip="H1", version="completa", bloque="E",
         dia="2025-02-01", diferencia=0.5, excluido=False, motivo=""):
    """Fila con el formato de diferencias() mas la columna simbolo."""
    return {"simbolo": simbolo, "tf": tf, "sentido": sentido, "hipotesis": hip, "version": version,
            "bloque": bloque, "costo": 0.0011, "dia": dia,
            "diferencia": np.nan if excluido else diferencia, "excluido": excluido, "motivo": motivo}


def test_resumen_agregado_una_fila_por_celda_declarada_y_bloque_presente():
    declaradas = celdas_declaradas()
    assert len(declaradas) == 76  # spec seccion 7: 19 versiones x 2 temporalidades x 2 sentidos
    filas = [fila(hip=h, version=v, tf=tf, sentido=s, simbolo=sim)
             for (h, v, tf, s) in declaradas for sim in ("BTC", "ETH")]
    filas.append(fila(hip="H1", version="completa", tf="1h", sentido="long", bloque="C1", dia="2025-09-01"))

    res = resumen_agregado(pd.DataFrame(filas), semilla=0)

    assert "simbolo" not in res.columns
    celdas = set(map(tuple, res[["hipotesis", "version", "tf", "sentido"]].drop_duplicates().to_numpy()))
    assert celdas == set(declaradas)
    assert len(res) == 76  # decision de Andres: 76 celdas, los bloques son columnas (no filas)


def test_resumen_agregado_cuenta_excluidos_por_motivo_y_n_mas_excluidos_es_el_total():
    filas = [
        fila(diferencia=0.5),                                              # contado
        fila(excluido=True, motivo="dedup"),                               # suprimido por deduplicar
        fila(excluido=True, motivo="menos de 20 candidatas validas"),      # sin referencia disponible
        fila(excluido=True, motivo="sin vela +8"),                         # datos faltantes
    ]
    res = resumen_agregado(pd.DataFrame(filas), semilla=0, celdas=[("H1", "completa", "1h", "long")])

    assert len(res) == 1  # el default es las 76 celdas declaradas; este test mira una sola
    r = res.iloc[0]
    assert r["n"] == 1
    assert r["excluidos_dedup"] == 1
    assert r["excluidos_sin_referencia"] == 1
    assert r["excluidos_datos_faltantes"] == 1
    assert r["n"] + r["excluidos_dedup"] + r["excluidos_sin_referencia"] + r["excluidos_datos_faltantes"] == len(filas)


def test_maximos_atr_long_short_y_sin_vela_mas_8():
    # ATR14 = 2 en todo el tramo (TR constante); i = 20 (posicion), horizonte 21..28, vela 29 fuera del horizonte.
    plana = (100, 101, 99, 100)
    filas = [plana] * 21 + [
        (100, 101, 99, 100),   # 21
        (100, 101, 99, 100),   # 22
        (100, 101, 99, 100),   # 23
        (100, 104, 99, 101),   # 24: maximo del horizonte = 104
        (100, 101, 99, 100),   # 25
        (100, 101, 97, 99),    # 26: minimo del horizonte = 97
        (100, 101, 99, 100),   # 27
        (100, 101, 99, 100),   # 28
        (100, 200, 1, 100),    # 29: fuera del horizonte, no debe contar
    ]
    df = velas(filas)

    # long: mfe = (104 - 100) / 2 = 2.0; mae = (100 - 97) / 2 = 1.5
    assert maximos_atr(df, 20, "long") == pytest.approx((2.0, 1.5))
    # short (espejo): mfe = (100 - 97) / 2 = 1.5; mae = (104 - 100) / 2 = 2.0
    assert maximos_atr(df, 20, "short") == pytest.approx((1.5, 2.0))

    # sin vela i+8 (la df termina en 28, i+8 = 28 no existe): NaN en ambos sentidos
    sin_plus8 = df.iloc[:28]
    for sentido in ("long", "short"):
        mfe, mae = maximos_atr(sin_plus8, 20, sentido)
        assert np.isnan(mfe) and np.isnan(mae)


def test_resumen_por_simbolo_una_fila_por_simbolo_y_celda_sin_cota_ni_significancia():
    filas = [
        fila(simbolo="BTC", diferencia=0.5),
        fila(simbolo="BTC", diferencia=0.1, dia="2025-02-02"),
        fila(simbolo="ETH", diferencia=-0.2),
        fila(simbolo="BTC", bloque="C1", diferencia=0.3, dia="2025-09-01"),
    ]
    res = resumen_por_simbolo(pd.DataFrame(filas), semilla=0)

    assert "simbolo" in res.columns
    assert len(res) == 3  # (BTC, E), (ETH, E), (BTC, C1)
    claves = res[["simbolo", "hipotesis", "version", "sentido", "tf", "bloque"]].drop_duplicates()
    assert len(claves) == 3
    assert not any(("cota" in c) or ("signif" in c) or ("p_valor" in c) for c in res.columns)


def test_resumen_por_simbolo_tres_costos_n_una_vez_y_sin_filas_repetidas_por_costo():
    base = [fila(simbolo="BTC", diferencia=0.5), fila(simbolo="BTC", diferencia=0.1, dia="2025-02-02", excluido=True,
                                                      motivo="dedup")]
    filas = []
    for costo in (0.0011, 0.0008, 0.0014):
        filas += [{**f, "costo": costo} for f in base]
    res = resumen_por_simbolo(pd.DataFrame(filas), semilla=0)

    assert len(res) == 1  # (BTC, H1, completa, 1h, long, E): el costo no multiplica filas
    assert not res.duplicated(["simbolo", "hipotesis", "version", "tf", "sentido", "bloque"]).any()
    r = res.iloc[0]
    assert r["n"] == 1  # n y excluidos salen una sola vez (del costo base)
    assert r["excluidos_dedup"] == 1
    assert r["mfe_medio"] != r["mfe_medio"]  # sin columna mfe en el df: NaN, como en el agregado
    for tag in ("base", "sens0008", "sens0014"):
        assert f"diferencia_media_{tag}" in res.columns
    assert r["diferencia_media_base"] == pytest.approx(0.5)  # una sola diferencia contada
