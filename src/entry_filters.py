"""
Filtro de entrada EMA10 / EMA10+T-Theory (2026-08-04), compartido entre el
bot en vivo (run_live_trading.py) y los backtests que lo validaron
(run_backtest_ema_ttheory.py, run_walkforward_hybrid.py) -- mismo código en
los dos lados para que lo que corre en vivo sea EXACTAMENTE lo que se
backtesteó, no una reimplementación aparte.
"""
import os
import sys

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "indicators"))
from indicators.trend import add_ema, ema_simple_bias
from indicators.t_theory import detect_base_and_t_window


def apply_entry_filter(setups: list, df_entry, mode: str) -> list:
    """mode: 'none' (sin filtro) / 'ema_only' (nunca contra EMA10) /
    'ema_t' (EMA10 + solo dentro de la ventana T de Terry Laundry)."""
    if mode == "none" or not setups:
        return setups

    df_ind = add_ema(df_entry.copy(), 10, "ema10")
    df_ind["ema10_bias"] = ema_simple_bias(df_ind, "ema10")
    if mode == "ema_t":
        df_ind = detect_base_and_t_window(df_ind)

    kept = []
    for s in setups:
        row = df_ind.iloc[s.signal_bar_pos]
        required_bias = "up" if s.direction == "long" else "down"
        if row["ema10_bias"] != required_bias:
            continue
        if mode == "ema_t" and not bool(row["in_t_window"]):
            continue
        kept.append(s)
    return kept
