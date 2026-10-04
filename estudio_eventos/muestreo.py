"""Deduplicacion, referencia al azar y bootstrap por dia."""
import numpy as np
import pandas as pd


def deduplicar(eventos: pd.DataFrame, ventana: int = 8) -> pd.DataFrame:
    """Columnas simbolo, tf, sentido, pos. Dentro de cada (simbolo, tf, sentido), descarta eventos a menos de 'ventana' velas del ultimo contado."""
    if eventos.empty:
        return eventos.copy()
    partes = []
    ordenados = eventos.sort_values(["simbolo", "tf", "sentido", "pos"])
    for _, grupo in ordenados.groupby(["simbolo", "tf", "sentido"], sort=False):
        ultimo = None
        mantener = []
        for pos in grupo["pos"].to_numpy():
            cuenta = ultimo is None or pos - ultimo > ventana
            if cuenta:
                ultimo = pos
            mantener.append(cuenta)
        partes.append(grupo[np.array(mantener, dtype=bool)])
    return pd.concat(partes).reset_index(drop=True)


def referencia_azar(df: pd.DataFrame, i_evento: int, sentido: str, excluir: np.ndarray, n: int = 20, semilla: int = 0) -> list:
    """Posiciones de n velas con la misma hora, bloque (columna 'bloque') y sentido (columna 'sentido') que i_evento, sin velas marcadas en 'excluir'. Semilla fija.

    'sentido' es el del evento ("long"/"short"); df debe traer la columna 'sentido' con la que se filtran las candidatas.
    Si hay menos de n candidatas devuelve lista vacia (el evento no tiene referencia y no se evalua).
    """
    hora = df.index.hour.to_numpy()
    bloque = df["bloque"].to_numpy()
    sentidos = df["sentido"].to_numpy()
    candidatas = np.flatnonzero((hora == hora[i_evento]) & (bloque == bloque[i_evento])
                                & (sentidos == sentido) & ~np.asarray(excluir, dtype=bool))
    candidatas = candidatas[candidatas != i_evento]
    if len(candidatas) < n:
        return []
    rng = np.random.default_rng([semilla, i_evento])
    return sorted(int(p) for p in rng.choice(candidatas, size=n, replace=False))


def bootstrap_dia(df: pd.DataFrame, columna: str, n_boot: int = 2000, semilla: int = 0, alpha: float = 0.05) -> tuple:
    """Remuestreo de dias (columna 'dia') con semilla propia. Devuelve (media, cota_inf, cota_sup).

    Estadistico: media de todos los eventos. Cada remuestreo elige dias con reemplazo y pondera sus eventos.
    """
    valores = df[columna].to_numpy(dtype=float)
    _, inversa = np.unique(df["dia"].to_numpy(), return_inverse=True)
    sumas = np.bincount(inversa, weights=valores)
    cuentas = np.bincount(inversa).astype(float)
    rng = np.random.default_rng(semilla)
    elegidos = rng.integers(0, len(sumas), size=(n_boot, len(sumas)))
    medias = sumas[elegidos].sum(axis=1) / cuentas[elegidos].sum(axis=1)
    lo, hi = np.quantile(medias, [alpha / 2, 1 - alpha / 2])
    return float(valores.mean()), float(lo), float(hi)
