"""Fase 0 del estudio de eventos: solo conteos de frecuencia, sin ninguna columna de resultado de precio.

Uso: python -m estudio_eventos.fase0
Escribe docs/estudio-eventos-frecuencia.md (tablas resumen). El registro (docs/estudio-eventos-registro.md)
se crea una sola vez; si ya existe, el script no lo toca (es solo agregar).
"""
import os

import numpy as np
import pandas as pd

from estudio_eventos.hipotesis import h1, h2, h3, h4, h5
from estudio_eventos.muestreo import deduplicar

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATOS = os.path.join(RAIZ, "data", "backtest_snapshot")
DOCS = os.path.join(RAIZ, "docs")

PRINCIPAL = ["ADA", "BNB", "BTC", "ETH", "HYPE", "LINK", "SOL", "XAUT"]
SECUNDARIO = ["NCCO1OILBRENT2USD", "NCCOXAG2USD", "NCSINASDAQ1002USD", "NCSISP5002USD", "NCSKAAPL2USD",
              "NCSKAMZN2USD", "NCSKGOOGL2USD", "NCSKMETA2USD", "NCSKNVDA2USD"]
BLOQUES = [("E", "2025-01-01", "2025-08-01"), ("C1", "2025-08-02", "2026-03-02"), ("C2", "2026-03-03", "2026-10-02")]
MINIMO_E = 30
FECHA_FASE0 = "2026-10-04"


def cargar(simbolo: str, tf: str) -> pd.DataFrame:
    d = pd.read_csv(os.path.join(DATOS, f"{simbolo}_USDT_USDT_{tf}.csv"))
    d.index = pd.to_datetime(d["datetime"], utc=True)
    return d[["open", "high", "low", "close", "volume"]].astype(float)


def diario(horaria: pd.DataFrame) -> pd.DataFrame:
    """Diario UTC armado desde 1h. Un dia con huecos (menos de 24 velas) no cuenta como dia completo."""
    g = horaria.resample("1D")
    d = pd.DataFrame({"open": g["open"].first(), "high": g["high"].max(), "low": g["low"].min(),
                      "close": g["close"].last(), "volume": g["volume"].sum(), "velas": g["close"].count()})
    return d[d["velas"] == 24].drop(columns="velas")


def especificaciones(mayor: pd.DataFrame, tf: str, dur_mayor: str):
    """19 versiones (seccion 3): cada una es (hipotesis, version, funcion(df, sentido))."""
    return [
        ("H1", "completa", lambda d, s: h1(d, s)),
        ("H1", "con_estructura_mayor", lambda d, s: h1(d, s, df_mayor=mayor, duracion_senal=tf, duracion_mayor=dur_mayor)),
        ("H1", "sin_rechazo", lambda d, s: h1(d, s, rechazo=False)),
        ("H1", "sin_fvg", lambda d, s: h1(d, s, fvg=False)),
        ("H2", "completa", lambda d, s: h2(d, s)),
        ("H2", "sin_adx", lambda d, s: h2(d, s, adx_filtro=False)),
        ("H2", "sin_volumen", lambda d, s: h2(d, s, volumen=False)),
        ("H2", "sin_fvg", lambda d, s: h2(d, s, fvg=False)),
        ("H3", "completa", lambda d, s: h3(d, s)),
        ("H3", "sin_volumen", lambda d, s: h3(d, s, volumen=False)),
        ("H3", "sin_fibonacci", lambda d, s: h3(d, s, fibonacci=False)),
        ("H3", "sin_fvg", lambda d, s: h3(d, s, fvg=False)),
        ("H4", "completa", lambda d, s: h4(d, s)),
        ("H4", "sin_volumen", lambda d, s: h4(d, s, volumen=False)),
        ("H4", "compresion_1_vela", lambda d, s: h4(d, s, duracion_minima=1)),
        ("H5", "base", lambda d, s: h5(d, s)),
        ("H5", "base_volumen_barrida", lambda d, s: h5(d, s, volumen_barrida=True)),
        ("H5", "base_fvg_ruptura", lambda d, s: h5(d, s, fvg_ruptura=True)),
        ("H5", "base_ambos", lambda d, s: h5(d, s, volumen_barrida=True, fvg_ruptura=True)),
    ]


def bloque_de(fechas: pd.DatetimeIndex) -> np.ndarray:
    dias = fechas.normalize()
    out = np.full(len(fechas), "", dtype=object)
    for nombre, desde, hasta in BLOQUES:
        mascara = (dias >= pd.Timestamp(desde, tz="UTC")) & (dias <= pd.Timestamp(hasta, tz="UTC"))
        out[np.asarray(mascara)] = nombre
    return out


def contar() -> pd.DataFrame:
    """Un renglon por evento deduplicado: universo, simbolo, tf, sentido, hipotesis, version, mes, bloque."""
    filas = []
    for universo, simbolos in (("principal", PRINCIPAL), ("secundario", SECUNDARIO)):
        for simbolo in simbolos:
            horaria = cargar(simbolo, "1h")
            cuatro = cargar(simbolo, "4h")
            casos = [("1h", horaria, cuatro, "4h"), ("4h", cuatro, diario(horaria), "1D")]
            for tf, df, mayor, dur_mayor in casos:
                for hip, version, fn in especificaciones(mayor, tf, dur_mayor):
                    evs = []
                    for sentido in ("long", "short"):
                        pos = np.flatnonzero(fn(df, sentido).to_numpy())
                        evs.append(pd.DataFrame({"simbolo": simbolo, "tf": tf, "sentido": sentido, "pos": pos}))
                    ev = deduplicar(pd.concat(evs, ignore_index=True))
                    if ev.empty:
                        continue
                    ev["universo"] = universo
                    ev["hipotesis"] = hip
                    ev["version"] = version
                    ev["fecha"] = df.index[ev["pos"].to_numpy()]
                    ev["mes"] = ev["fecha"].dt.strftime("%Y-%m")
                    ev["bloque"] = bloque_de(pd.DatetimeIndex(ev["fecha"]))
                    filas.append(ev.drop(columns=["pos", "fecha"]))
    total = pd.concat(filas, ignore_index=True)
    return total[total["bloque"] != ""].reset_index(drop=True)


def tabla_celdas(total: pd.DataFrame) -> pd.DataFrame:
    tab = total.pivot_table(index=["hipotesis", "version", "tf", "sentido"], columns=["universo", "bloque"],
                            values="simbolo", aggfunc="count", fill_value=0)
    tab.columns = [f"{'prin' if u == 'principal' else 'sec'}_{b}" for u, b in tab.columns]
    for c in ["prin_E", "prin_C1", "prin_C2", "sec_C1", "sec_C2"]:
        if c not in tab.columns:
            tab[c] = 0
    tab = tab[["prin_E", "prin_C1", "prin_C2", "sec_C1", "sec_C2"]].reset_index()
    tab["evaluable"] = np.where(tab["prin_E"] >= MINIMO_E, "si", "no evaluable")
    return tab


def markdown(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    lineas = ["| " + " | ".join(str(c) for c in cols) + " |", "|" + "---|" * len(cols)]
    for _, fila in df.iterrows():
        lineas.append("| " + " | ".join(str(v) for v in fila.values) + " |")
    return "\n".join(lineas)


def escribir_frecuencia(total: pd.DataFrame, celdas: pd.DataFrame) -> None:
    completas = total[total["version"].isin(["completa", "base"])]
    meses = sorted(total["mes"].unique())
    simbolo_mes = completas[completas["universo"] == "principal"].pivot_table(
        index="simbolo", columns="mes", values="tf", aggfunc="count", fill_value=0)
    simbolo_mes = simbolo_mes.reindex(columns=[m for m in meses if m in simbolo_mes.columns], fill_value=0)
    simbolo_mes = simbolo_mes.reset_index()
    sec = completas[completas["universo"] == "secundario"].pivot_table(
        index="simbolo", columns="bloque", values="tf", aggfunc="count", fill_value=0).reset_index()
    texto = [
        "# Estudio de eventos: frecuencia (fase 0)",
        "",
        f"Generado el {FECHA_FASE0} con `python -m estudio_eventos.fase0`. Solo conteos de eventos deduplicados (8 velas). "
        "Ninguna columna de resultado de precio. Fuente: `data/backtest_snapshot/` (1h y 4h; el diario se arma desde 1h). "
        "Universo principal = cripto, HYPE, XAUT, SOL (datos desde 2025). Universo secundario = NC* (solo C1 y C2, reportado aparte).",
        "",
        "Regla: celdas con menos de 30 eventos en E (universo principal) se marcan como **no evaluable**.",
        "",
        "## Tabla 1: conteo por hipotesis, version, temporalidad y sentido",
        "",
        markdown(celdas),
        "",
        "## Tabla 2: principal, por simbolo y mes (solo versiones completas: H1-H4 `completa` y H5 `base`; suma de 1h/4h y sentidos)",
        "",
        markdown(simbolo_mes),
        "",
        "## Tabla 3: secundario NC* por bloque (solo versiones completas; no entra al criterio de fase 1)",
        "",
        markdown(sec),
        "",
    ]
    with open(os.path.join(DOCS, "estudio-eventos-frecuencia.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(texto))


def escribir_registro(celdas: pd.DataFrame) -> None:
    ruta = os.path.join(DOCS, "estudio-eventos-registro.md")
    if os.path.exists(ruta):
        raise SystemExit("El registro ya existe: es solo agregar, no se regenera desde el script.")
    filas = celdas.copy()
    filas.insert(0, "fase", "0 (frecuencia)")
    filas.insert(0, "fecha", FECHA_FASE0)
    texto = [
        "# Registro de pruebas del estudio de eventos",
        "",
        "Solo agregar: cada celda evaluada en una fase queda aqui con su resultado, aunque no pase. Nunca editar lo escrito.",
        "N declarado: 76 celdas reales (5 hipotesis, 19 versiones x 2 sentidos x 2 temporalidades). Ver spec seccion 7.",
        "",
        "Columnas: conteos de eventos deduplicados. prin = universo principal; sec = NC* (sin E).",
        "",
        markdown(filas),
        "",
    ]
    with open(ruta, "w", encoding="utf-8") as f:
        f.write("\n".join(texto))


def main() -> None:
    total = contar()
    celdas = tabla_celdas(total)
    escribir_frecuencia(total, celdas)
    escribir_registro(celdas)
    print(celdas.to_string(index=False))


if __name__ == "__main__":
    main()
