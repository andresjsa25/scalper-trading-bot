"""
Fractales, swings y detección de barridos de liquidez (sweeps).
Base común para las 3 estrategias -- mismo fractal clásico de Williams
que usa fibo-reversal-bot (N=2, 5 velas), reimplementado acá porque este
es un proyecto separado.
"""
import numpy as np
import pandas as pd


def find_raw_fractals(df: pd.DataFrame, n: int = 2) -> pd.DataFrame:
    df = df.copy()
    highs = df["high"].values
    lows = df["low"].values
    n_rows = len(df)

    is_fractal_high = np.zeros(n_rows, dtype=bool)
    is_fractal_low = np.zeros(n_rows, dtype=bool)

    for i in range(n, n_rows - n):
        window_high = highs[i - n: i + n + 1]
        window_low = lows[i - n: i + n + 1]
        if highs[i] == window_high.max() and np.sum(window_high == highs[i]) == 1:
            is_fractal_high[i] = True
        if lows[i] == window_low.min() and np.sum(window_low == lows[i]) == 1:
            is_fractal_low[i] = True

    df["fractal_high"] = is_fractal_high
    df["fractal_low"] = is_fractal_low
    return df


def build_zigzag_swings(df: pd.DataFrame) -> pd.DataFrame:
    """Secuencia alternante de swings confirmados (estilo ZigZag)."""
    swings = []
    last_type = None

    for i in range(len(df)):
        is_h = df["fractal_high"].iloc[i]
        is_l = df["fractal_low"].iloc[i]
        if not is_h and not is_l:
            continue
        candidates = []
        if is_h:
            candidates.append(("high", df["high"].iloc[i]))
        if is_l:
            candidates.append(("low", df["low"].iloc[i]))

        for kind, price in candidates:
            if last_type is None:
                swings.append({"pos": i, "datetime": df["datetime"].iloc[i], "price": price, "type": kind})
                last_type = kind
            elif kind == last_type:
                if kind == "high" and price > swings[-1]["price"]:
                    swings[-1] = {"pos": i, "datetime": df["datetime"].iloc[i], "price": price, "type": kind}
                elif kind == "low" and price < swings[-1]["price"]:
                    swings[-1] = {"pos": i, "datetime": df["datetime"].iloc[i], "price": price, "type": kind}
            else:
                swings.append({"pos": i, "datetime": df["datetime"].iloc[i], "price": price, "type": kind})
                last_type = kind

    return pd.DataFrame(swings)


def compute_swing_legs_pct(swings: pd.DataFrame) -> pd.DataFrame:
    """
    % de movimiento de cada swing respecto al swing anterior (tramo
    a->b). Igual idea que fibo-reversal-bot/src/indicators/fractals.py
    (compute_swing_legs), simplificado sin calibración walk-forward:
    percentil estático sobre toda la muestra del símbolo.
    """
    s = swings.sort_values("pos").reset_index(drop=True)
    pct_move = [None] * len(s)
    for i in range(1, len(s)):
        a_price = s.loc[i - 1, "price"]
        b_price = s.loc[i, "price"]
        pct_move[i] = abs(b_price - a_price) / a_price * 100
    s["pct_move"] = pct_move
    return s


def filter_sweeps_by_min_swing_pct(sweeps: pd.DataFrame, swings_with_pct: pd.DataFrame,
                                    min_percentile: float) -> pd.DataFrame:
    """
    Filtra los eventos de barrido para quedarse solo con los que barren un
    swing "significativo" (pct_move del swing >= percentil `min_percentile`
    sobre todos los swings del símbolo). min_percentile=0 -> sin filtro.
    """
    if min_percentile <= 0 or len(sweeps) == 0:
        return sweeps

    valid_pct = swings_with_pct["pct_move"].dropna()
    if len(valid_pct) < 10:  # muestra insuficiente para un percentil confiable
        return sweeps
    threshold = np.percentile(valid_pct, min_percentile)

    pct_by_pos = dict(zip(swings_with_pct["pos"], swings_with_pct["pct_move"]))
    keep = sweeps["swing_pos"].map(lambda p: (pct_by_pos.get(p) or 0) >= threshold)
    return sweeps[keep].reset_index(drop=True)


def detect_liquidity_sweeps(df: pd.DataFrame, swings: pd.DataFrame) -> pd.DataFrame:
    """
    Para cada swing confirmado (fractal alternante), busca la PRIMERA vela
    posterior que "toma" ese nivel (mecha por encima de un swing high, o
    por debajo de un swing low). Sin look-ahead: el swing debe estar
    confirmado (posición ya pasada en el df) antes de poder ser barrido.

    Devuelve un DataFrame de eventos: pos (vela que barre), swing_type
    ('high'/'low'), level_price, swing_pos (vela del swing original).
    """
    events = []
    highs = df["high"].values
    lows = df["low"].values
    n = len(df)

    active_high = None  # {'price':, 'swing_pos':}
    active_low = None

    swing_iter = swings.sort_values("pos").reset_index(drop=True)
    next_swing_idx = 0

    for i in range(n):
        # activar swings ya confirmados hasta esta posición
        while next_swing_idx < len(swing_iter) and swing_iter.loc[next_swing_idx, "pos"] <= i:
            row = swing_iter.loc[next_swing_idx]
            if row["type"] == "high":
                active_high = {"price": row["price"], "swing_pos": int(row["pos"])}
            else:
                active_low = {"price": row["price"], "swing_pos": int(row["pos"])}
            next_swing_idx += 1

        if active_high is not None and highs[i] > active_high["price"] and i > active_high["swing_pos"]:
            events.append({"pos": i, "swing_type": "high", "level_price": active_high["price"],
                            "swing_pos": active_high["swing_pos"]})
            active_high = None  # se consume, no se vuelve a barrer el mismo nivel

        if active_low is not None and lows[i] < active_low["price"] and i > active_low["swing_pos"]:
            events.append({"pos": i, "swing_type": "low", "level_price": active_low["price"],
                            "swing_pos": active_low["swing_pos"]})
            active_low = None

    return pd.DataFrame(events)
