"""
Indicador "T" de Terry Laundry (T-Theory), versión de simetría temporal
aplicada sobre el propio precio -- confirmado con el usuario (2026-08-04)
porque la formulación original (sobre datos de amplitud NYSE/S&P) no
aplica directo a activos individuales como los que operamos.

Concepto (T-Theory clásico): se mide la duración de una fase de
acumulación/consolidación (la "base"), y se proyecta que el movimiento
posterior dure un tiempo SIMÉTRICO a esa base -- el punto "T" es donde se
espera que el movimiento se agote. Como filtro de entrada: solo se opera
a favor de una ruptura mientras siga DENTRO de su ventana T proyectada
(no se persigue un movimiento que ya duró más de lo que su propia base
sugería).
"""
import numpy as np
import pandas as pd

BASE_WINDOW = 8            # velas mínimas para considerar una "base" (mismo criterio que detect_range en V3)
MAX_BASE_RANGE_PCT = 0.6   # qué tan angosto debe ser el rango para contar como base


def detect_base_and_t_window(df: pd.DataFrame, base_window: int = BASE_WINDOW,
                              max_range_pct: float = MAX_BASE_RANGE_PCT) -> pd.DataFrame:
    """
    Para cada vela, determina si sigue vigente la "ventana T" de la última
    base detectada: cuántas velas duró esa base (T) y cuántas velas pasaron
    desde que terminó (edad). in_t_window = True mientras edad <= T.
    Sin look-ahead: la base se confirma recién en la vela donde termina
    (se rompe el rango), y desde ahí se cuenta la ventana T hacia adelante.
    """
    df = df.copy()
    n = len(df)
    typical_range = (df["high"] - df["low"]).rolling(50, min_periods=10).mean()
    roll_high = df["high"].rolling(base_window).max()
    roll_low = df["low"].rolling(base_window).min()
    range_width = roll_high - roll_low
    is_base = (range_width <= (typical_range * base_window * max_range_pct)).fillna(False)

    t_duration = [None] * n       # duración (en velas) de la última base confirmada
    bars_since_base_end = [None] * n
    in_t_window = [False] * n

    current_base_start = None
    current_t = None
    base_end_pos = None

    for i in range(n):
        if is_base.iloc[i]:
            if current_base_start is None:
                current_base_start = i - base_window + 1
        else:
            if current_base_start is not None:
                # la base recién terminada dura desde current_base_start hasta i-1
                current_t = i - current_base_start
                base_end_pos = i - 1
                current_base_start = None

        if current_t is not None and base_end_pos is not None:
            age = i - base_end_pos
            t_duration[i] = current_t
            bars_since_base_end[i] = age
            in_t_window[i] = age <= current_t

    df["t_duration"] = t_duration
    df["bars_since_base_end"] = bars_since_base_end
    df["in_t_window"] = in_t_window
    return df
