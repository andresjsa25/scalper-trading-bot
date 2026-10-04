"""Resumen agregado: costo como columnas (76 filas, base y sensibilidades; spec seccion 5 y 7)."""
import os
import sys

import numpy as np
import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from estudio_eventos.fase0 import celdas_declaradas  # noqa: E402
from estudio_eventos.diferencia import COSTO_BASE, intervalo_diferencia, resumen_agregado  # noqa: E402

COSTOS = [COSTO_BASE, 0.0008, 0.0014]


def fila(simbolo="BTC", tf="1h", sentido="long", hip="H1", version="completa", bloque="E",
         dia="2025-02-01", diferencia=0.5, costo=COSTO_BASE, excluido=False, motivo="", mfe=1.0, mae=0.5):
    return {"simbolo": simbolo, "tf": tf, "sentido": sentido, "hipotesis": hip, "version": version,
            "bloque": bloque, "costo": costo, "dia": dia,
            "diferencia": np.nan if excluido else diferencia, "excluido": excluido, "motivo": motivo,
            "mfe": mfe, "mae": mae}


def test_tres_costos_dan_76_filas_y_columnas_base_y_sensibilidades():
    declaradas = celdas_declaradas()
    filas = [fila(hip=h, version=v, tf=tf, sentido=s, costo=c, simbolo=sim)
             for (h, v, tf, s) in declaradas for c in COSTOS for sim in ("BTC", "ETH")]
    res = resumen_agregado(pd.DataFrame(filas), semilla=0, celdas=declaradas)

    assert len(res) == 76
    assert "costo" not in res.columns
    for tag in ("base", "sens0008", "sens0014"):
        for stat in ("diferencia_media", "cota_inferior", "cota_superior"):
            assert f"{stat}_E_{tag}" in res.columns


def test_columna_base_decide_y_sensibilidades_usan_su_propio_costo():
    base = [fila(diferencia=0.5), fila(diferencia=0.7, dia="2025-02-02")]
    sens08 = [fila(diferencia=0.9, costo=0.0008), fila(diferencia=1.1, costo=0.0008, dia="2025-02-02")]
    sens14 = [fila(diferencia=0.2, costo=0.0014), fila(diferencia=0.4, costo=0.0014, dia="2025-02-02")]
    res = resumen_agregado(pd.DataFrame(base + sens08 + sens14), semilla=0, celdas=[("H1", "completa", "1h", "long")])

    assert len(res) == 1
    r = res.iloc[0]
    media_base, lo_base, hi_base = intervalo_diferencia(pd.DataFrame(base), semilla=0)
    assert r["diferencia_media_E_base"] == media_base == pytest.approx(0.6)
    assert (r["cota_inferior_E_base"], r["cota_superior_E_base"]) == (lo_base, hi_base)
    assert r["diferencia_media_E_sens0008"] == pytest.approx(1.0)
    assert r["diferencia_media_E_sens0014"] == pytest.approx(0.3)
