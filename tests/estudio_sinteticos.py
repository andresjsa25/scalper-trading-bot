"""Constructores de velas sinteticas para los tests del estudio de eventos (sin red, sin data/)."""
import numpy as np
import pandas as pd

COLUMNAS = ["open", "high", "low", "close", "volume"]


def velas(filas, inicio="2025-01-01 00:00", freq="1h"):
    """Filas (open, high, low, close[, volume]); volumen por defecto 100. Indice UTC."""
    idx = pd.date_range(inicio, periods=len(filas), freq=freq, tz="UTC")
    datos = [tuple(f[:4]) + ((f[4] if len(f) > 4 else 100.0),) for f in filas]
    return pd.DataFrame(datos, index=idx, columns=COLUMNAS, dtype=float)


def con_prefijo(filas, precio, n=25):
    """Antepone n velas planas (volumen 100) para que el volumen medio de 20 velas tenga historia."""
    return [(precio, precio, precio, precio)] * n + list(filas)


def tendencia(n, inicio, paso):
    """n velas que avanzan 'paso' por vela desde 'inicio' (sin mechas)."""
    filas, previo = [], inicio
    for _ in range(n):
        c = previo + paso
        filas.append((previo, max(previo, c), min(previo, c), c))
        previo = c
    return filas


def zigzag(puntos):
    """Velas que unen pivotes (posicion, precio). Cierre en el pivote; mecha de 0,2 solo en el pivote."""
    filas, previo = [], puntos[0][1]
    tramos = list(zip(puntos, puntos[1:]))
    for k in range(puntos[0][0], puntos[-1][0] + 1):
        c = next(v0 + (v1 - v0) * (k - p0) / (p1 - p0) for (p0, v0), (p1, v1) in tramos if p0 <= k <= p1)
        o = previo
        cima = any(p == k and 0 < idx < len(puntos) - 1 and v > puntos[idx - 1][1] and v > puntos[idx + 1][1]
                   for idx, (p, v) in enumerate(puntos))
        valle = any(p == k and 0 < idx < len(puntos) - 1 and v < puntos[idx - 1][1] and v < puntos[idx + 1][1]
                    for idx, (p, v) in enumerate(puntos))
        filas.append((o, max(o, c) + (0.2 if cima else 0.0), min(o, c) - (0.2 if valle else 0.0), c))
        previo = c
    return filas


def aleatorio(n, semilla, inicio="2025-01-01 00:00", freq="1h"):
    """Caminata aleatoria OHLCV con semilla fija (para pruebas de no-futuro)."""
    rng = np.random.default_rng(semilla)
    cierres = 100 + np.cumsum(rng.normal(0, 0.6, n))
    aperturas = np.concatenate([[100.0], cierres[:-1]])
    altos = np.maximum(aperturas, cierres) + np.abs(rng.normal(0, 0.3, n))
    bajos = np.minimum(aperturas, cierres) - np.abs(rng.normal(0, 0.3, n))
    volumen = rng.uniform(50, 500, n)
    idx = pd.date_range(inicio, periods=n, freq=freq, tz="UTC")
    return pd.DataFrame({"open": aperturas, "high": altos, "low": bajos, "close": cierres, "volume": volumen},
                        index=idx, columns=COLUMNAS)


def invertir(df, c=1000.0):
    """Espejo de precios (p' = c - p): convierte cada patron largo en su version corta."""
    return pd.DataFrame({"open": c - df["open"], "high": c - df["low"], "low": c - df["high"],
                         "close": c - df["close"], "volume": df["volume"]}, index=df.index, columns=COLUMNAS)
