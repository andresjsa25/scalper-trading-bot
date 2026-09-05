"""
Patrones de entrada extraídos de los 3 videos analizados. Cada función
está comentada con la regla EXACTA tal como se describió verbalmente en
la transcripción del video correspondiente -- son traducciones a código
de una explicación hablada (no una confirmación visual pixel-a-pixel del
gráfico), así que quedan documentadas para que el usuario las pueda
corregir si no calzan con lo que muestra el video.
"""
import numpy as np
import pandas as pd


# ============================================================
# Video 1 (BELIKETHEALGO): cambio de estructura (CHoCH) + FVG
# ============================================================

def detect_fvg(df: pd.DataFrame) -> pd.DataFrame:
    """
    Fair Value Gap / desequilibrio: secuencia de 3 velas donde la vela 1 y
    la vela 3 no se tocan (deja un hueco). Alcista: high[i-2] < low[i].
    Bajista: low[i-2] > high[i]. Se marca en la posición de la vela 3 (i).
    """
    df = df.copy()
    high = df["high"].values
    low = df["low"].values
    n = len(df)

    fvg_bull = [False] * n
    fvg_bear = [False] * n
    fvg_bull_top = [None] * n     # límite superior del hueco (= low[i])
    fvg_bull_bottom = [None] * n  # límite inferior del hueco (= high[i-2])
    fvg_bear_top = [None] * n
    fvg_bear_bottom = [None] * n

    for i in range(2, n):
        if high[i - 2] < low[i]:
            fvg_bull[i] = True
            fvg_bull_top[i] = low[i]
            fvg_bull_bottom[i] = high[i - 2]
        if low[i - 2] > high[i]:
            fvg_bear[i] = True
            fvg_bear_top[i] = low[i - 2]
            fvg_bear_bottom[i] = high[i]

    df["fvg_bull"] = fvg_bull
    df["fvg_bear"] = fvg_bear
    df["fvg_bull_top"] = fvg_bull_top
    df["fvg_bull_bottom"] = fvg_bull_bottom
    df["fvg_bear_top"] = fvg_bear_top
    df["fvg_bear_bottom"] = fvg_bear_bottom
    return df


def find_choch_after_sweep(df: pd.DataFrame, sweep_pos: int, sweep_type: str,
                            max_lookahead: int, swings_by_type: dict):
    """
    Busca el cambio de estructura (CHoCH) posterior a un barrido, usando
    los swings internos (fractales) de la MISMA temporalidad de entrada.

    sweep_type='high' (barrimos un máximo -> buscamos ventas): CHoCH = la
    primera vela, después del swing, cuyo cierre rompe por debajo del
    último swing low interno confirmado antes de esa vela.
    sweep_type='low' (buscamos compras): CHoCH = cierre por encima del
    último swing high interno.

    `swings_by_type` = {"high": (pos_array, price_array), "low": (pos_array,
    price_array)} -- numpy arrays ya separados por tipo y ordenados por
    posición (ver `generate_setups` en strategy_v1_sniper.py).

    Dos optimizaciones sobre la versión original (misma lógica, mismo
    resultado -- ver historial 2026-08-26, encontrado en vivo con los
    índices sintéticos NCSISP500/NCSINASDAQ100: 40-55s por ciclo contra <1s
    en el resto de los símbolos):
      1. El filtro+sort por tipo se calcula UNA vez afuera (antes se
         recalculaba en cada llamada -- esta función se llama una vez POR
         CADA barrido detectado).
      2. El puntero de swings arranca con busqueda binaria (`np.searchsorted`)
         en la posición de `sweep_pos`, en vez de recorrer linealmente desde
         el principio en cada llamada. Antes, para barridos tardíos (pos
         alto) con muchos swings previos, cada llamada re-caminaba miles de
         posiciones ya vistas en llamadas anteriores -- con cientos de
         barridos eso se volvía cuadrático. Ahora el arranque es O(log n) y
         el resto del recorrido queda acotado por max_lookahead, como
         siempre fue la intención.

    Devuelve la posición del CHoCH (int) o None si no ocurre dentro de
    max_lookahead velas.
    """
    close = df["close"].values
    target_type = "low" if sweep_type == "high" else "high"
    swing_pos_arr, swing_price_arr = swings_by_type[target_type]

    end_pos = min(sweep_pos + max_lookahead, len(df) - 1)
    swing_ptr = int(np.searchsorted(swing_pos_arr, sweep_pos, side="right"))
    last_level = swing_price_arr[swing_ptr - 1] if swing_ptr > 0 else None

    for i in range(sweep_pos, end_pos + 1):
        while swing_ptr < len(swing_pos_arr) and swing_pos_arr[swing_ptr] <= i:
            last_level = swing_price_arr[swing_ptr]
            swing_ptr += 1
        if last_level is None:
            continue
        if sweep_type == "high" and close[i] < last_level:
            return i
        if sweep_type == "low" and close[i] > last_level:
            return i
    return None


# ============================================================
# Video 2 (SANCHEZZFX): Liquidity Swift + vela envolvente
# ============================================================

def detect_liquidity_swift(df: pd.DataFrame) -> pd.DataFrame:
    """
    "La vela se mete dentro de la vela de la izquierda, no hace falta que
    cierre por fuera": mecha que barre el low/high de la vela anterior
    pero el CIERRE vuelve a quedar dentro del rango de esa vela anterior.
    Bullish (barrido de low): low[i] < low[i-1] and close[i] > low[i-1].
    Bearish (barrido de high): high[i] > high[i-1] and close[i] < high[i-1].
    """
    df = df.copy()
    n = len(df)
    swift_bull = [False] * n
    swift_bear = [False] * n
    low = df["low"].values
    high = df["high"].values
    close = df["close"].values

    for i in range(1, n):
        if low[i] < low[i - 1] and close[i] > low[i - 1]:
            swift_bull[i] = True
        if high[i] > high[i - 1] and close[i] < high[i - 1]:
            swift_bear[i] = True

    df["liquidity_swift_bull"] = swift_bull
    df["liquidity_swift_bear"] = swift_bear
    return df


def detect_engulfing(df: pd.DataFrame) -> pd.DataFrame:
    """
    Vela envolvente CON CUERPO (no mecha) -- confirmado visualmente contra
    el video (SANCHEZZFX): el CIERRE de la vela actual debe superar la
    APERTURA de la última vela "con intención" de signo contrario. No hace
    falta que el open de la vela actual esté dentro del cuerpo anterior
    (esa condición extra que tenía antes no está en el video, se sacó).
    Bullish: close[i-1] < open[i-1] (i-1 bajista), close[i] > open[i]
    (i alcista), close[i] >= open[i-1].
    """
    df = df.copy()
    n = len(df)
    engulf_bull = [False] * n
    engulf_bear = [False] * n
    o = df["open"].values
    c = df["close"].values

    for i in range(1, n):
        prev_bear = c[i - 1] < o[i - 1]
        prev_bull = c[i - 1] > o[i - 1]
        curr_bull = c[i] > o[i]
        curr_bear = c[i] < o[i]
        if prev_bear and curr_bull and c[i] >= o[i - 1]:
            engulf_bull[i] = True
        if prev_bull and curr_bear and c[i] <= o[i - 1]:
            engulf_bear[i] = True

    df["engulfing_bull"] = engulf_bull
    df["engulfing_bear"] = engulf_bear
    return df


# ============================================================
# Video 3 (Pol Castella): rango (AMD) + Turtle Soup + Breaker Block
# ============================================================

def detect_range(df: pd.DataFrame, window: int = 8, max_range_pct: float = 0.6) -> pd.DataFrame:
    """
    Rango de acumulación: últimas `window` velas contenidas dentro de un
    rango (high-low) angosto, comparado contra el ATR-like promedio de
    rango de las últimas 50 velas (max_range_pct = qué tan angosto,
    proporción del rango típico). Marca range_high/range_low vigentes.
    """
    df = df.copy()
    typical_range = (df["high"] - df["low"]).rolling(50, min_periods=10).mean()
    roll_high = df["high"].rolling(window).max()
    roll_low = df["low"].rolling(window).min()
    range_width = roll_high - roll_low

    is_range = range_width <= (typical_range * window * max_range_pct)
    df["range_high"] = roll_high.where(is_range)
    df["range_low"] = roll_low.where(is_range)
    df["in_range"] = is_range.fillna(False)
    return df


def detect_turtle_soup(df: pd.DataFrame) -> pd.DataFrame:
    """
    Turtle Soup: la vela barre (mecha) el rango vigente (range_high o
    range_low de detect_range, tomado de la vela anterior) y CIERRA de
    vuelta dentro del rango. Señal de reversión hacia el lado contrario.
    """
    df = df.copy()
    n = len(df)
    soup_bull = [False] * n   # barrió range_low, buscamos compras
    soup_bear = [False] * n   # barrió range_high, buscamos ventas
    low = df["low"].values
    high = df["high"].values
    close = df["close"].values
    range_low_prev = df["range_low"].shift(1).values
    range_high_prev = df["range_high"].shift(1).values

    for i in range(n):
        rl = range_low_prev[i]
        rh = range_high_prev[i]
        if rl == rl and low[i] < rl and close[i] > rl:  # rl==rl descarta NaN
            soup_bull[i] = True
        if rh == rh and high[i] > rh and close[i] < rh:
            soup_bear[i] = True

    df["turtle_soup_bull"] = soup_bull
    df["turtle_soup_bear"] = soup_bear
    return df
