"""Hipotesis H1-H5 y sus versiones (seccion 3 de la spec). Devuelven una Serie bool en la vela de senal."""
import pandas as pd


def h1(df: pd.DataFrame, direccion: str, rechazo: bool = True, fvg: bool = True,
       df_mayor: pd.DataFrame | None = None, duracion_senal: str = "1h", duracion_mayor: str = "4h") -> pd.Series:
    """RSI<30 + FVG vigente/sin rellenar/tocado + vela de rechazo. Con df_mayor: filtro de estructura mayor alineada."""
    raise NotImplementedError


def h2(df: pd.DataFrame, direccion: str, adx_filtro: bool = True, volumen: bool = True, fvg: bool = True) -> pd.Series:
    """ADX<20 + low<=banda inferior con cierre por encima + FVG vigente/sin rellenar/tocado + volumen alto."""
    raise NotImplementedError


def h3(df: pd.DataFrame, direccion: str, volumen: bool = True, fibonacci: bool = True, fvg: bool = True) -> pd.Series:
    """Barrida de liquidez + volumen alto + cierre en zona de Fibonacci + FVG vigente y sin rellenar."""
    raise NotImplementedError


def h4(df: pd.DataFrame, direccion: str, volumen: bool = True, duracion_minima: int = 6) -> pd.Series:
    """Compresion (ancho Bollinger percentil <=20 de 100 velas, >= duracion_minima velas seguidas) + cierre fuera del maximo/minimo de la compresion."""
    raise NotImplementedError


def h5(df: pd.DataFrame, direccion: str, volumen_barrida: bool = False, fvg_ruptura: bool = False) -> pd.Series:
    """Barrida en S; senal = primera vela en S+1..S+12 que cierra sobre el ultimo maximo confirmado antes de S, sin low menor al de S."""
    raise NotImplementedError
