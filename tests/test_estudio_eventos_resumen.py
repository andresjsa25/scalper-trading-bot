"""Intervalo por dia sobre la diferencia y resumen por celda (spec seccion 5, criterio 5)."""
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from estudio_eventos.diferencia import intervalo_diferencia  # noqa: E402


def _res(n=60, seed=5):
    rng = np.random.default_rng(seed)
    dias = [f"2025-01-{1 + k // 3:02d}" for k in range(n)]
    return pd.DataFrame({
        "dia": dias,
        "diferencia": rng.normal(0.1, 1.0, n),
        "excluido": [k % 7 == 0 for k in range(n)],
    })


def test_intervalo_diferencia_es_reproducible_con_la_misma_semilla():
    res = _res()
    assert intervalo_diferencia(res, semilla=11) == intervalo_diferencia(res, semilla=11)


def test_intervalo_ignora_excluidos():
    res = _res()
    media, _, _ = intervalo_diferencia(res, semilla=11)
    validos = res.loc[~res["excluido"]]
    assert media == float(validos["diferencia"].mean())


def test_resumen_celdas_una_fila_por_celda_y_contiene_la_media():
    from estudio_eventos.diferencia import resumen_celdas

    partes = []
    for hipotesis, dif, seed in (("H1", 0.5, 1), ("H2", -0.3, 2)):
        r = _res(seed=seed)
        r["diferencia"] = r["diferencia"] + dif
        r["simbolo"], r["tf"], r["sentido"] = "BTC", "1h", "long"
        r["hipotesis"], r["version"], r["bloque"], r["costo"] = hipotesis, "completa", "prin_E", 0.0011
        partes.append(r)
    res = pd.concat(partes, ignore_index=True)

    tabla = resumen_celdas(res, semilla=3)
    assert len(tabla) == 2
    assert list(tabla.columns) == ["simbolo", "tf", "sentido", "hipotesis", "version", "bloque", "costo",
                                   "n", "diferencia_media", "cota_inferior", "cota_superior"]
    for _, fila in tabla.iterrows():
        assert fila["cota_inferior"] <= fila["diferencia_media"] <= fila["cota_superior"]
        assert fila["n"] == int((~res.loc[res["hipotesis"] == fila["hipotesis"], "excluido"]).sum())
