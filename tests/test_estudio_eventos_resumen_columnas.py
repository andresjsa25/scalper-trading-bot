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


def test_universo_principal_no_mezcla_nc_y_resumen_nc_solo_tiene_nc():
    from estudio_eventos.fase0 import PRINCIPAL, SECUNDARIO

    df = pd.DataFrame([fila(simbolo="BTC", diferencia=0.5),
                       fila(simbolo="NCSKAAPL2USD", bloque="C1", dia="2025-09-01", diferencia=-0.4)])
    declaradas = [("H1", "completa", "1h", "long")]

    agregado = resumen_agregado(df, semilla=0, celdas=declaradas)
    assert agregado.loc[0, "n_E"] == 1 and agregado.loc[0, "n_C1"] == 0  # el NC* de C1 no entra

    secundario = resumen_agregado(df, semilla=0, celdas=declaradas, universo=SECUNDARIO)
    assert len(secundario) == 1
    assert secundario.loc[0, "n_C1"] == 1 and secundario.loc[0, "n_E"] == 0
    assert "BTC" in PRINCIPAL and "NCSKAAPL2USD" in SECUNDARIO


def test_default_de_celdas_es_las_76_declaradas_aunque_el_df_tenga_pocas():
    res = resumen_agregado(pd.DataFrame([fila(diferencia=0.5)]), semilla=0)
    assert len(res) == 76
    assert set(map(tuple, res[["hipotesis", "version", "tf", "sentido"]].to_numpy())) == set(celdas_declaradas())


def test_n_media_y_mfe_a_mano_con_filas_excluidas():
    filas = [
        fila(diferencia=1.0, mfe=1.0, mae=0.2),
        fila(diferencia=2.0, mfe=2.0, mae=0.4, dia="2025-02-02"),
        fila(diferencia=3.0, mfe=3.0, mae=0.6, dia="2025-02-03"),
        fila(excluido=True, motivo="sin vela +8", mfe=100.0, mae=100.0, dia="2025-02-04"),
    ]
    res = resumen_agregado(pd.DataFrame(filas), semilla=0, celdas=[("H1", "completa", "1h", "long")])
    r = res.iloc[0]
    assert r["n_E"] == 3
    assert r["excluidos_datos_faltantes"] == 1
    assert r["diferencia_media_E_base"] == pytest.approx(2.0)
    assert r["mfe_medio_E"] == pytest.approx(2.0)  # la fila excluida (mfe 100) no entra
    assert r["mae_medio_E"] == pytest.approx(0.4)


def test_diferencias_mfe_mae_coinciden_con_maximos_atr():
    from estudio_eventos.diferencia import COSTO_BASE, diferencias, maximos_atr
    from estudio_sinteticos import aleatorio

    df = aleatorio(80, semilla=7)
    df["bloque"] = "E"
    df["sentido"] = "long"
    eventos = pd.DataFrame({"pos": [30, 45, 60], "sentido": ["long", "long", "long"]})
    res = diferencias(df, eventos, costo=COSTO_BASE)
    for _, r in res.iterrows():
        mfe, mae = maximos_atr(df, int(r["pos"]), r["sentido"])
        assert r["mfe"] == pytest.approx(mfe)
        assert r["mae"] == pytest.approx(mae)
