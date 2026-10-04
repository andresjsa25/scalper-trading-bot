"""Indicadores y pivotes confirmados (solo usan velas hasta la posición actual)."""
import pandas as pd


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    """RSI de Wilder."""
    raise NotImplementedError


def adx(df: pd.DataFrame, n: int = 14) -> pd.Series:
    """ADX de Wilder."""
    raise NotImplementedError


def bollinger(close: pd.Series, n: int = 20, k: float = 2.0) -> pd.DataFrame:
    """Bandas de Bollinger sobre SMA. Columnas: media, superior, inferior, ancho ((sup-inf)/media)."""
    raise NotImplementedError


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    """ATR de Wilder."""
    raise NotImplementedError


def pivotes_confirmados(df: pd.DataFrame, n: int = 3) -> pd.DataFrame:
    """Pivotes con n velas a cada lado. Columnas pivot_max y pivot_min: el precio del pivote en la fila j+n (cuando queda confirmado), NaN en el resto."""
    raise NotImplementedError
