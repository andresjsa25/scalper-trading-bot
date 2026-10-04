"""Fase 1 del estudio de eventos: guardas, criterio por celda, chequeo n + excluidos = crudos y universo principal (datos sinteticos)."""
import os
import sys

import numpy as np
import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from estudio_sinteticos import aleatorio  # noqa: E402
from estudio_eventos import fase1  # noqa: E402
from estudio_eventos.fase0 import PRINCIPAL  # noqa: E402
from estudio_eventos.diferencia import CLAVE_CELDA, resumen_agregado  # noqa: E402
from estudio_eventos.fase1 import calcular, crudos_por_celda, criterio, main, tabla_fase1, verificar_conteos  # noqa: E402


def fila(simbolo="ADA", dia="2025-02-01", diferencia=0.5, hip="H1", version="completa", tf="1h", sentido="long",
         excluido=False, motivo=""):
    """Fila con el formato de diferencias() mas simbolo, bloque E y costo base (una fila por evento)."""
    return {"simbolo": simbolo, "hipotesis": hip, "version": version, "tf": tf, "sentido": sentido,
            "costo": 0.0011, "bloque": "E", "dia": dia, "diferencia": np.nan if excluido else diferencia,
            "excluido": excluido, "motivo": motivo, "mfe": np.nan if excluido else 1.0, "mae": np.nan if excluido else 1.0}


def dias(n):
    return list(pd.date_range("2025-02-01", periods=n).strftime("%Y-%m-%d"))


def filas_celda(valores, hip="H1", version="completa", tf="1h", sentido="long", simbolo="ADA"):
    return [fila(simbolo=simbolo, dia=d, diferencia=v, hip=hip, version=version, tf=tf, sentido=sentido)
            for d, v in zip(dias(len(valores)), valores)]


def tabla_de(df):
    resumen = resumen_agregado(df)
    return tabla_fase1(verificar_conteos(resumen, crudos_por_celda(df[df["simbolo"].isin(PRINCIPAL)])))


def fila_de(tabla, hip, version, tf, sentido):
    return tabla[(tabla["hipotesis"] == hip) & (tabla["version"] == version) & (tabla["tf"] == tf) & (tabla["sentido"] == sentido)].iloc[0]


def test_plan_sin_flag_no_escribe_ni_lee_datos(tmp_path, monkeypatch, capsys):
    """(a) Sin --ejecutar-fase1 solo imprime el plan: no lee datos y no escribe nada."""
    monkeypatch.setattr(fase1, "DOCS", str(tmp_path))
    def no_leer(*a, **k):
        raise AssertionError("no debe leer datos sin el flag")
    monkeypatch.setattr(fase1, "cargar", no_leer)
    main([])
    salida = capsys.readouterr().out
    assert "NO EJECUTADO" in salida and "76" in salida
    assert os.listdir(tmp_path) == []


def test_flag_sin_aprobador_falla_antes_de_leer_datos(tmp_path, monkeypatch):
    """Con el flag pero sin --aprobada-por, el script sale con error y no toca datos ni docs."""
    monkeypatch.setattr(fase1, "DOCS", str(tmp_path))
    monkeypatch.setattr(fase1, "cargar", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no leer")))
    with pytest.raises(SystemExit):
        main(["--ejecutar-fase1"])
    assert os.listdir(tmp_path) == []


def test_celda_con_menos_de_30_eventos_es_no_evaluable():
    """(b) n < 30 en E: no evaluable, aunque la diferencia sea muy positiva."""
    df = pd.DataFrame(filas_celda([5.0] * 10))
    t = tabla_de(df)
    fila_ = fila_de(t, "H1", "completa", "1h", "long")
    assert fila_["n_E"] == 10
    assert fila_["resultado"] == "no evaluable"
    assert criterio(29, 1.0) == "no evaluable"


def test_pasa_con_cota_positiva_y_no_pasa_con_cota_menor_o_igual_a_cero():
    """(c) n >= 30 y cota > 0 pasa; media positiva pero cota <= 0 no pasa; media negativa no pasa."""
    alternado = [5.0 if i % 2 == 0 else -4.5 for i in range(40)]  # media 0,25 con mucha dispersion: cota < 0
    df = pd.DataFrame(filas_celda([0.5] * 40, hip="H1") + filas_celda(alternado, hip="H2") + filas_celda([-0.5] * 40, hip="H3"))
    t = tabla_de(df)
    assert fila_de(t, "H1", "completa", "1h", "long")["resultado"] == "pasa"
    assert fila_de(t, "H2", "completa", "1h", "long")["resultado"] == "no pasa"
    assert fila_de(t, "H3", "completa", "1h", "long")["resultado"] == "no pasa"
    assert criterio(40, 0.0) == "no pasa"


def test_chequeo_n_mas_excluidos_igual_a_crudos_falla_fuerte():
    """(d) Si n + excluidos no cuadra con los eventos crudos de la celda, el script falla y no sigue."""
    filas = filas_celda([0.5] * 35) + [fila(dia="2026-01-01", excluido=True, motivo="dedup")]
    df = pd.DataFrame(filas)
    cuentas = crudos_por_celda(df)
    assert verificar_conteos(resumen_agregado(df), cuentas) is not None  # cuadra: no falla
    cuentas_mal = cuentas.copy()
    cuentas_mal.loc[cuentas_mal["hipotesis"] == "H1", "crudos"] += 1  # un evento crudo de mas
    with pytest.raises(RuntimeError, match="no sigue"):
        verificar_conteos(resumen_agregado(df), cuentas_mal)


def test_universo_nc_no_entra_aunque_este_en_los_datos():
    """(e) Una fila NC* con valores enormes en la misma celda no cambia n ni la media de cripto."""
    cripto = filas_celda([0.5] * 40)
    nc = filas_celda([100.0] * 40, simbolo="NCSKAAPL2USD")
    t_sin = tabla_de(pd.DataFrame(cripto))
    t_con = tabla_de(pd.DataFrame(cripto + nc))
    a, b = fila_de(t_sin, "H1", "completa", "1h", "long"), fila_de(t_con, "H1", "completa", "1h", "long")
    assert b["n_E"] == a["n_E"] == 40
    assert b["dif_E_base"] == pytest.approx(0.5)
    assert b["resultado"] == a["resultado"]


def test_calcular_camino_completo_cuadra_y_excluye_nc():
    """Camino completo (velas -> dedup -> diferencias -> resumen) sobre datos sinteticos: los conteos cuadran y NC* no aparece."""
    velas = {"ADA": (aleatorio(600, 1), aleatorio(150, 1, freq="4h")),
             "NCSKAAPL2USD": (aleatorio(600, 2), aleatorio(150, 2, freq="4h"))}
    dif, crudos = calcular(velas)
    assert "NCSKAAPL2USD" not in set(dif["simbolo"]) and "NCSKAAPL2USD" not in set(crudos["simbolo"])
    assert len(crudos) > 0
    m = verificar_conteos(resumen_agregado(dif), crudos_por_celda(crudos))
    tabla = tabla_fase1(m)
    assert len(tabla) == 76
    assert set(tabla["resultado"]) <= {"pasa", "no pasa", "no evaluable"}
