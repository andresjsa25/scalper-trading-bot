"""Deduplicacion, referencia al azar y bootstrap por dia."""
import numpy as np
import pandas as pd


def deduplicar(eventos: pd.DataFrame, ventana: int = 8) -> pd.DataFrame:
    """Columnas simbolo, tf, sentido, pos. Dentro de cada (simbolo, tf, sentido), descarta eventos a menos de 'ventana' velas del ultimo contado."""
    raise NotImplementedError


def referencia_azar(df: pd.DataFrame, i_evento: int, excluir: np.ndarray, n: int = 20, semilla: int = 0) -> list:
    """Posiciones de n velas con la misma hora y bloque (columna 'bloque') que i_evento, sin velas marcadas en 'excluir'. Semilla fija."""
    raise NotImplementedError


def bootstrap_dia(df: pd.DataFrame, columna: str, n_boot: int = 2000, semilla: int = 0, alpha: float = 0.05) -> tuple:
    """Remuestreo de dias (columna 'dia') con semilla propia. Devuelve (media, cota_inf, cota_sup)."""
    raise NotImplementedError
