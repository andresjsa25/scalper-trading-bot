"""Definiciones de la seccion 3 de la spec. direccion: 'long' o 'short' (espejo)."""
import pandas as pd


def volumen_alto(df: pd.DataFrame, factor: float = 1.5, n: int = 20) -> pd.Series:
    """True si volume >= factor * media de los n volumenes anteriores (sin contar la vela actual)."""
    raise NotImplementedError


def formacion_fvg(df: pd.DataFrame, direccion: str) -> pd.Series:
    """True en la vela j de un FVG formado (alcista: low[j] > high[j-2]; bajista: high[j] < low[j-2])."""
    raise NotImplementedError


def fvg_en(df: pd.DataFrame, i: int, direccion: str, ventana: int = 24, tocado: bool = True):
    """Zona (bajo, alto) del FVG vigente en i (formado en la ventana), sin rellenar por velas previas a i y tocado por la vela i; None si no hay."""
    raise NotImplementedError


def vela_rechazo(df: pd.DataFrame, direccion: str) -> pd.Series:
    """Martillo (mecha >= 2x cuerpo, cierre en mitad superior) o envolvente alcista (espejo para short)."""
    raise NotImplementedError


def estructura_mayor_alineada(df_mayor: pd.DataFrame, instante: pd.Timestamp, direccion: str, duracion: pd.Timedelta, n: int = 3) -> bool:
    """Usa solo velas de df_mayor cerradas en 'instante'; True si el ultimo minimo (max en short) confirmado es mas alto (bajo) que el anterior."""
    raise NotImplementedError


def barrida_liquidez(df: pd.DataFrame, direccion: str, n: int = 3) -> pd.Series:
    """True si la vela hace low por debajo (high por encima) del ultimo pivote confirmado y cierra por encima (debajo)."""
    raise NotImplementedError


def zona_fibonacci(df: pd.DataFrame, i: int, direccion: str, n: int = 3) -> bool:
    """True si el cierre de la vela i cae en [H-0.618R, H-0.5R] del ultimo tramo confirmado L->H (R=H-L). Espejo para short."""
    raise NotImplementedError
