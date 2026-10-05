"""Fase 1 del estudio de eventos: exploracion en el bloque E, universo principal (spec seccion 6 y anexo).

NO SE CORRE sobre datos reales sin el OK de Andres. Sin --ejecutar-fase1 solo imprime el plan y sale:
no lee datos ni escribe nada. Con --ejecutar-fase1 es obligatorio --aprobada-por NOMBRE.

Uso (solo con aprobacion de Andres):
    python -m estudio_eventos.fase1 --ejecutar-fase1 --aprobada-por NOMBRE

Escribe docs/estudio-eventos-fase1.md (solo tablas resumen, sin eventos crudos ni retornos por evento) y
agrega una seccion fechada a docs/estudio-eventos-registro.md (solo agregar, nunca editar filas viejas).
El NC* (universo secundario) no entra en esta fase.
"""
import argparse
import datetime
import os

import numpy as np
import pandas as pd

from estudio_eventos.diferencia import CLAVE_CELDA, COSTO_BASE, COSTOS_SENSIBILIDAD, diferencias, resumen_agregado
from estudio_eventos.fase0 import DOCS, MINIMO_E, PRINCIPAL, bloque_de, cargar, celdas_declaradas, diario, especificaciones, markdown
from estudio_eventos.muestreo import deduplicar

BLOQUE = "E"
DESDE, HASTA = "2025-01-01", "2025-08-01"
COLUMNAS_EXCLUIDOS = ["excluidos_dedup", "excluidos_sin_referencia", "excluidos_datos_faltantes"]


def criterio(n: int, cota_inferior: float) -> str:
    """Spec seccion 6, fase 1: 'pasa' si n >= 30 y la cota inferior 95 % del costo base es > 0."""
    if n < MINIMO_E:
        return "no evaluable"
    return "pasa" if cota_inferior > 0 else "no pasa"


def _celdas_simbolo(simbolo: str, horaria: pd.DataFrame, cuatro: pd.DataFrame):
    """Por (tf, hipotesis, version): (tf, hip, version, velas, eventos E). Dedup sobre toda la serie (como fase 0) y luego se filtra a E.
    Columna 'contado': False para los eventos que la deduplicacion suprime."""
    for tf, df, mayor, dur_mayor in [("1h", horaria, cuatro, "4h"), ("4h", cuatro, diario(horaria), "1D")]:
        for hip, version, fn in especificaciones(mayor, tf, dur_mayor):
            ev = pd.concat([pd.DataFrame({"sentido": s, "pos": np.flatnonzero(fn(df, s).to_numpy())})
                            for s in ("long", "short")], ignore_index=True)
            ev["simbolo"], ev["tf"], ev["hipotesis"], ev["version"] = simbolo, tf, hip, version
            cont = deduplicar(ev[["simbolo", "tf", "sentido", "pos"]])
            contadas = set(zip(cont["sentido"], cont["pos"]))
            ev["contado"] = np.array([(s, p) in contadas for s, p in zip(ev["sentido"], ev["pos"])], dtype=bool)
            ev["bloque"] = bloque_de(df.index[ev["pos"].to_numpy(dtype=int)])
            yield tf, hip, version, df, ev[ev["bloque"] == BLOQUE].reset_index(drop=True)


def calcular(velas: dict) -> tuple:
    """velas: {simbolo: (horaria 1h, cuatro 4h)}. Solo entra el universo PRINCIPAL (las claves NC* se ignoran).
    Devuelve (diferencias por evento, crudos E por evento). Los suprimidos por dedup van como excluido=True, motivo 'dedup'."""
    dif, crudos = [], []
    for simbolo in [s for s in PRINCIPAL if s in velas]:
        horaria, cuatro = velas[simbolo]
        for tf, hip, version, df, ev in _celdas_simbolo(simbolo, horaria, cuatro):
            crudos.append(ev[["simbolo", "tf", "hipotesis", "version", "sentido"]])
            df = df.assign(bloque=bloque_de(df.index))
            for sentido in ("long", "short"):
                dfs = df.assign(sentido=sentido)
                e = ev[ev["sentido"] == sentido]
                contados, suprimidos = e[e["contado"]], e[~e["contado"]]
                pos_sup = suprimidos["pos"].to_numpy(dtype=int)
                for costo in [COSTO_BASE, *COSTOS_SENSIBILIDAD.values()]:
                    res = diferencias(dfs, contados[["pos", "sentido"]], costo)
                    sup = pd.DataFrame({"pos": pos_sup, "sentido": sentido, "dia": df.index[pos_sup].strftime("%Y-%m-%d"),
                                        "diferencia": np.nan, "excluido": True, "motivo": "dedup",
                                        "mfe": np.nan, "mae": np.nan})
                    dif.append(pd.concat([res, sup], ignore_index=True).assign(
                        simbolo=simbolo, tf=tf, hipotesis=hip, version=version, costo=costo, bloque=BLOQUE))
    return pd.concat(dif, ignore_index=True), pd.concat(crudos, ignore_index=True)


def crudos_por_celda(crudos: pd.DataFrame) -> pd.DataFrame:
    return crudos.groupby(CLAVE_CELDA).size().rename("crudos").reset_index()


def verificar_conteos(resumen: pd.DataFrame, cuentas: pd.DataFrame) -> pd.DataFrame:
    """Chequeo fuerte: n + excluidos de cada celda debe igualar sus eventos crudos. Si no cuadra, falla (no sigue)."""
    m = resumen.merge(cuentas, on=CLAVE_CELDA, how="left")
    m["crudos"] = m["crudos"].fillna(0).astype(int)
    suma = m[["n", *COLUMNAS_EXCLUIDOS]].sum(axis=1)
    malas = m[suma != m["crudos"]]
    if not malas.empty:
        raise RuntimeError(f"n + excluidos != eventos crudos en {len(malas)} celdas; no sigue. "
                           f"Primera: {malas[CLAVE_CELDA].iloc[0].to_dict()}")
    return m


def tabla_fase1(m: pd.DataFrame) -> pd.DataFrame:
    """Una fila por celda (76). Costo base decide; sensibilidades 0,0008 y 0,0014 como columnas de solo lectura."""
    t = pd.DataFrame({
        "hipotesis": m["hipotesis"], "version": m["version"], "tf": m["tf"], "sentido": m["sentido"],
        "crudos_E": m["crudos"], "n_E": m["n_E"],
        "excluidos_dedup": m["excluidos_dedup"], "excluidos_sin_referencia": m["excluidos_sin_referencia"],
        "excluidos_datos_faltantes": m["excluidos_datos_faltantes"],
        "dif_E_base": m["diferencia_media_E_base"], "cota_inf_E_base": m["cota_inferior_E_base"],
        "dif_E_sens0008": m["diferencia_media_E_sens0008"], "cota_inf_E_sens0008": m["cota_inferior_E_sens0008"],
        "dif_E_sens0014": m["diferencia_media_E_sens0014"], "cota_inf_E_sens0014": m["cota_inferior_E_sens0014"],
    })
    t["resultado"] = [criterio(int(n), c) for n, c in zip(t["n_E"], t["cota_inf_E_base"])]
    return t


def plan() -> str:
    return "\n".join([
        "Fase 1 (exploracion, bloque E, universo principal). ESTADO: NO EJECUTADO.",
        f"Universo: {', '.join(PRINCIPAL)} (NC* fuera de esta fase).",
        f"Bloque: E ({DESDE} a {HASTA}). Celdas: {len(celdas_declaradas())} (hipotesis x version x tf x sentido).",
        f"Costo base: {COSTO_BASE}; sensibilidades: {', '.join(str(c) for c in COSTOS_SENSIBILIDAD.values())}.",
        f"Criterio: pasa si n_E >= {MINIMO_E} y cota inferior 95 % (costo base) > 0; n_E < {MINIMO_E} = no evaluable.",
        "Salidas: docs/estudio-eventos-fase1.md (tablas) y seccion nueva en docs/estudio-eventos-registro.md.",
        "Sin --ejecutar-fase1 no se leen datos ni se escribe nada.",
        "Para correrla hace falta el OK de Andres: --ejecutar-fase1 --aprobada-por NOMBRE.",
    ])


def escribir_fase1(tabla: pd.DataFrame, aprobada_por: str, fecha: str) -> None:
    texto = [
        "# Estudio de eventos: fase 1 (exploracion, bloque E)",
        "",
        f"Generado el {fecha} con `python -m estudio_eventos.fase1`. Aprobada por: {aprobada_por}.",
        "Universo principal (8 simbolos: ADA, BNB, BTC, ETH, HYPE, LINK, SOL, XAUT) juntos dentro de cada celda. NC* no entra.",
        "Criterio: pasa si n_E >= 30 y cota inferior 95 % del costo base > 0. Sensibilidades solo de lectura.",
        "",
        markdown(tabla),
        "",
    ]
    with open(os.path.join(DOCS, "estudio-eventos-fase1.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(texto))


def agregar_registro(tabla: pd.DataFrame, aprobada_por: str, fecha: str) -> None:
    ruta = os.path.join(DOCS, "estudio-eventos-registro.md")
    if not os.path.exists(ruta):
        raise SystemExit("Falta el registro: no se crea desde fase 1.")
    filas = tabla[["hipotesis", "version", "tf", "sentido", "n_E", "cota_inf_E_base", "resultado"]].copy()
    filas.insert(0, "fase", "1 (exploracion E)")
    filas.insert(0, "fecha", fecha)
    with open(ruta, "a", encoding="utf-8") as f:
        f.write(f"\n## Fase 1 ({fecha}, aprobada por {aprobada_por})\n\n{markdown(filas)}\n")


def ejecutar(aprobada_por: str, fecha: str) -> pd.DataFrame:
    if os.path.exists(os.path.join(DOCS, "estudio-eventos-fase1.md")):
        raise SystemExit("Fase 1 ya corrida: docs/estudio-eventos-fase1.md existe. El bloque E se explora una sola vez; no se vuelve a correr.")
    velas = {s: (cargar(s, "1h"), cargar(s, "4h")) for s in PRINCIPAL}
    dif, crudos = calcular(velas)
    resumen = resumen_agregado(dif, universo=PRINCIPAL)
    tabla = tabla_fase1(verificar_conteos(resumen, crudos_por_celda(crudos)))
    escribir_fase1(tabla, aprobada_por, fecha)
    agregar_registro(tabla, aprobada_por, fecha)
    return tabla


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description="Fase 1 del estudio de eventos. Sin --ejecutar-fase1 solo imprime el plan.")
    p.add_argument("--ejecutar-fase1", action="store_true")
    p.add_argument("--aprobada-por", default=None)
    args = p.parse_args(argv)
    if not args.ejecutar_fase1:
        print(plan())
        return
    if not args.aprobada_por:
        p.error("--aprobada-por es obligatorio con --ejecutar-fase1")
    tabla = ejecutar(args.aprobada_por, datetime.date.today().isoformat())
    print(tabla["resultado"].value_counts().to_string())


if __name__ == "__main__":
    main()
