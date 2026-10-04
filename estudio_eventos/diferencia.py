"""Diferencia por evento: retorno en ATR neto de costos menos la media de su referencia al azar (spec seccion 5 y anexo)."""
import numpy as np
import pandas as pd

from estudio_eventos.indicadores import atr
from estudio_eventos.muestreo import bootstrap_dia, referencia_azar

HORIZONTE = 8


def _retornos(df: pd.DataFrame, sentido: str, costo: float) -> np.ndarray:
    """ret_atr de cada posicion i; NaN si falta la vela i+1, la i+8 o el ATR."""
    s = 1.0 if sentido == "long" else -1.0
    n = len(df)
    opens = df["open"].to_numpy(dtype=float)
    closes = df["close"].to_numpy(dtype=float)
    entrada = np.full(n, np.nan)
    entrada[:-1] = opens[1:]
    salida = np.full(n, np.nan)
    salida[: n - HORIZONTE] = closes[HORIZONTE:]
    with np.errstate(invalid="ignore", divide="ignore"):
        return (s * (salida - entrada) - costo * entrada) / atr(df).to_numpy(dtype=float)


def retorno_atr(df: pd.DataFrame, i: int, sentido: str, costo: float) -> float:
    """ret_atr = (s*(close[i+8] - open[i+1]) - costo*open[i+1]) / ATR14[i].

    df: velas OHLC (columnas open, high, low, close) con indice temporal; i es la posicion (iloc) de la vela de senal.
    sentido: "long" (s = +1) o "short" (s = -1). costo: fraccion de ida y vuelta (base 0,0011; sensibilidad 0,0008 y 0,0014).
    ATR14[i]: ATR de Wilder hasta la vela i (solo usa velas <= i). Devuelve NaN si no hay vela i+1 o i+8.
    """
    return float(_retornos(df, sentido, costo)[i])


def diferencias(df: pd.DataFrame, eventos: pd.DataFrame, costo: float, semilla: int = 0, n: int = 20) -> pd.DataFrame:
    """Diferencia por evento = ret_atr(evento) - media(ret_atr de sus n candidatas al azar).

    df: velas de un (simbolo, temporalidad) con columnas open, high, low, close, bloque y sentido.
        La columna 'sentido' es la que usa referencia_azar para filtrar candidatas: una llamada por sentido.
    eventos: DataFrame con columnas 'pos' (posicion iloc en df) y 'sentido' ("long"/"short"),
        ya deduplicado con deduplicar(). Los eventos que el llamador pasa son los contados (decision de Andres: solo contados;
    las velas de eventos suprimidos por dedup pueden ser candidatas).
    Alcance de la exclusion (decision de Andres): solo las velas de la celda que el llamador pasa en 'eventos'
    (hipotesis x sentido x temporalidad x bloque), no las de todas las hipotesis.
    costo: fraccion de ida y vuelta. semilla: semilla fija de la referencia al azar.
    Devuelve un DataFrame con una fila por evento de entrada y columnas al menos:
        pos (int), sentido (str), diferencia (float, NaN si excluido), excluido (bool), motivo (str; vacio si no excluido).
    Un evento excluido (sin vela +8, o con menos de n candidatas validas) queda en el resultado con excluido=True.
    """
    n_velas = len(df)
    posiciones = eventos["pos"].to_numpy(dtype=int)
    marcadas = np.zeros(n_velas, dtype=bool)
    marcadas[posiciones] = True  # velas con evento: no son candidatas
    filas = []
    for pos, sentido in zip(posiciones, eventos["sentido"].to_numpy()):
        ret = _retornos(df, sentido, costo)
        candidatas_excluidas = marcadas | ~np.isfinite(ret)
        mfe, mae = maximos_atr(df, int(pos), sentido)
        fila = {"pos": int(pos), "sentido": sentido, "dia": df.index[pos].strftime("%Y-%m-%d"),
                "diferencia": np.nan, "excluido": False, "motivo": "", "mfe": mfe, "mae": mae}
        if pos + HORIZONTE >= n_velas:
            fila.update(excluido=True, motivo="sin vela +8")
        elif not np.isfinite(ret[pos]):
            fila.update(excluido=True, motivo="ATR no disponible")
        else:
            cands = referencia_azar(df, pos, sentido, candidatas_excluidas, n=n, semilla=semilla)
            if not cands:
                fila.update(excluido=True, motivo=f"menos de {n} candidatas validas")
            else:
                fila["diferencia"] = float(ret[pos] - ret[cands].mean())
        filas.append(fila)
    return pd.DataFrame(filas, columns=["pos", "sentido", "dia", "diferencia", "excluido", "motivo", "mfe", "mae"])


def intervalo_diferencia(res: pd.DataFrame, semilla: int = 0) -> tuple:
    """(media, cota_inf, cota_sup) 95% por dia de la 'diferencia' de los eventos no excluidos. Semilla fija."""
    validos = res.loc[~res["excluido"].astype(bool)]
    if validos.empty:
        return (np.nan, np.nan, np.nan)
    return bootstrap_dia(validos, "diferencia", semilla=semilla)


COLUMNAS_CELDA = ["simbolo", "tf", "sentido", "hipotesis", "version", "bloque", "costo"]


def resumen_celdas(df: pd.DataFrame, semilla: int = 0) -> pd.DataFrame:
    """Una fila por celda: n (no excluidos), diferencia_media y cota 95% por dia (semilla fija).

    df: diferencias de varias celdas, con columnas COLUMNAS_CELDA, 'dia', 'diferencia' y 'excluido'.
    """
    filas = []
    for clave, grupo in df.groupby(COLUMNAS_CELDA, sort=True, dropna=False):
        media, lo, hi = intervalo_diferencia(grupo, semilla=semilla)
        n = int((~grupo["excluido"].astype(bool)).sum())
        filas.append({**dict(zip(COLUMNAS_CELDA, clave)), "n": n,
                      "diferencia_media": media, "cota_inferior": lo, "cota_superior": hi})
    return pd.DataFrame(filas, columns=COLUMNAS_CELDA + ["n", "diferencia_media", "cota_inferior", "cota_superior"])


def maximos_atr(df: pd.DataFrame, i: int, sentido: str) -> tuple:
    """(mfe, mae) descriptivos en unidades de ATR14[i], horizonte i+1..i+8, sin costos, entrada = open[i+1].

    long:  mfe = (max(high[i+1..i+8]) - open[i+1]) / ATR14[i];  mae = (open[i+1] - min(low[i+1..i+8])) / ATR14[i]
    short: mfe = (open[i+1] - min(low[i+1..i+8])) / ATR14[i];  mae = (max(high[i+1..i+8]) - open[i+1]) / ATR14[i]
    mae positivo = en contra. Sin vela i+8 o sin ATR: (NaN, NaN). El motivo "datos faltantes" lo asigna el llamador.
    """
    if i + HORIZONTE >= len(df):
        return (np.nan, np.nan)
    a = float(atr(df).iloc[i])
    if not np.isfinite(a) or a <= 0:
        return (np.nan, np.nan)
    entrada = float(df["open"].iloc[i + 1])
    maximo = float(df["high"].iloc[i + 1: i + 1 + HORIZONTE].max())
    minimo = float(df["low"].iloc[i + 1: i + 1 + HORIZONTE].min())
    if sentido == "long":
        return ((maximo - entrada) / a, (entrada - minimo) / a)
    return ((entrada - minimo) / a, (maximo - entrada) / a)


def resumen_agregado(df: pd.DataFrame, semilla: int = 0) -> pd.DataFrame:
    """Una fila por celda agregada SIN simbolo: hipotesis, version, sentido, tf, bloque, costo (todos los simbolos juntos).

    df: filas de diferencias de varios simbolos, con columnas COLUMNAS_CELDA + 'simbolo', 'dia', 'diferencia', 'excluido' y 'motivo'.
        Los eventos suprimidos por dedup se pasan como filas con excluido=True y motivo="dedup".
    Motivos de exclusion (motivo de diferencias -> columna): "dedup" -> excluidos_dedup;
        "menos de 20 candidatas validas" -> excluidos_sin_referencia;
        "sin vela +8" y "ATR no disponible" -> excluidos_datos_faltantes.
    Columnas: COLUMNAS_CELDA + n (no excluidos), excluidos_dedup, excluidos_sin_referencia, excluidos_datos_faltantes,
        diferencia_media, cota_inferior, cota_superior (bootstrap por dia, semilla fija). Invariante: n + excluidos = filas de la celda.
    """
    raise NotImplementedError


def resumen_por_simbolo(df: pd.DataFrame, semilla: int = 0) -> pd.DataFrame:
    """Detalle descriptivo: el mismo conteo que resumen_agregado pero una fila por (simbolo, celda). Sin cota ni significancia.

    Columnas: simbolo + COLUMNAS_CELDA + n, excluidos_dedup, excluidos_sin_referencia, excluidos_datos_faltantes, diferencia_media.
    """
    raise NotImplementedError
