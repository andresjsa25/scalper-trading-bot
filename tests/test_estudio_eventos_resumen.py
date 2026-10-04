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
