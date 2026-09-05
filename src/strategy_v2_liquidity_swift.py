"""
Estrategia V2 -- "Liquidity Swift + envolvente" (video SANCHEZZFX).

El video usa 3 temporalidades en cascada (H4 -> H1 -> M5). Este proyecto
solo tiene 2 (1h de contexto, 15min de entrada), así que la cascada se
adapta a 2 pasos -- ADAPTACIÓN MÍA, no está en el video tal cual:
  1. En 1h (equivalente combinado de su H4+H1): barrido de un nivel
     estructural (swing fractal) + Liquidity Swift en esa misma vela
     (mecha que barre la vela anterior pero cierra de vuelta adentro).
  2. En 15min (equivalente a su M5): vela ENVOLVENTE con cuerpo (no mecha)
     sobre la última vela "con intención" contraria, dentro de la ventana
     de sesión. Esa vela es el gatillo de entrada, al cierre.

Gestión: SL ajustado, confirmado visualmente contra el video (min 16:00):
va en el extremo de la MECHA de la vela que hizo el barrido de liquidez
(NO en la vela envolvente -- eso era un error, corregido). TP = config.TP_RR_RATIO.
"""
import os
import sys

import pandas as pd

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "indicators"))
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from indicators.liquidity import (
    find_raw_fractals, build_zigzag_swings, detect_liquidity_sweeps,
    compute_swing_legs_pct, filter_sweeps_by_min_swing_pct,
)
from indicators.patterns import detect_liquidity_swift, detect_engulfing
from session_filter import in_session
from backtest import TradeSetup

ENGULFING_SEARCH_WINDOW_BARS = 32  # ~8h en 15min para que aparezca la envolvente tras el swift
SETUP_VALIDITY_BARS = 48           # ~12h en 15min para que la operación se resuelva
STOP_BUFFER_PCT = 0.0005
MIN_SWING_PERCENTILE = 0


def prepare(df_context: pd.DataFrame, df_entry: pd.DataFrame, min_swing_percentile: float = MIN_SWING_PERCENTILE):
    df_context = find_raw_fractals(df_context.copy(), n=2)
    context_swings = build_zigzag_swings(df_context)
    context_sweeps = detect_liquidity_sweeps(df_context, context_swings)

    swings_with_pct = compute_swing_legs_pct(context_swings)
    context_sweeps = filter_sweeps_by_min_swing_pct(context_sweeps, swings_with_pct, min_swing_percentile)

    df_context = detect_liquidity_swift(df_context)
    df_entry = detect_engulfing(df_entry.copy())
    return df_context, context_sweeps, df_entry


def generate_setups(symbol: str, df_context: pd.DataFrame, df_entry: pd.DataFrame,
                     min_swing_percentile: float = MIN_SWING_PERCENTILE) -> list:
    df_context, context_sweeps, df_entry = prepare(df_context, df_entry, min_swing_percentile)
    setups = []
    entry_datetimes = df_entry["datetime"]

    for _, sweep in context_sweeps.sort_values("pos").iterrows():
        pos = int(sweep["pos"])
        sweep_type = sweep["swing_type"]
        direction = "short" if sweep_type == "high" else "long"

        # Confirmación combinada 1h (barrido + liquidity swift en la misma vela).
        # Probé permitir el swift en una ventana de hasta 6 velas DESPUÉS del
        # barrido (interpretando "después de haber eliminado... es ver un
        # liquidity Swift" de forma más laxa) y el resultado empeoró mucho
        # (más señales, pero de peor calidad -- PF cayó en los 10 activos).
        # Revertido a "misma vela" hasta poder confirmarlo visualmente.
        swift_col = "liquidity_swift_bear" if direction == "short" else "liquidity_swift_bull"
        if not df_context[swift_col].iloc[pos]:
            continue

        sweep_dt = df_context.iloc[pos]["datetime"]
        entry_start_idx = int(entry_datetimes.searchsorted(sweep_dt))
        if entry_start_idx >= len(df_entry):
            continue

        engulf_col = "engulfing_bear" if direction == "short" else "engulfing_bull"
        trigger_pos = None
        search_end = min(entry_start_idx + ENGULFING_SEARCH_WINDOW_BARS, len(df_entry) - 1)
        for k in range(entry_start_idx, search_end + 1):
            if not df_entry[engulf_col].iloc[k]:
                continue
            if not in_session(df_entry.iloc[k]["datetime"]):
                continue
            trigger_pos = k
            break
        if trigger_pos is None:
            continue

        bar = df_entry.iloc[trigger_pos]
        entry_price = bar["close"]  # entra al cierre de la vela envolvente

        # Stop en la mecha de la vela de 1h que hizo el barrido (pos), no en
        # la vela envolvente -- confirmado visualmente (min 16:00, "pegaíto"
        # al extremo de la estructura de rechazo, no al mínimo de la entrada).
        sweep_bar = df_context.iloc[pos]
        if direction == "short":
            stop_price = sweep_bar["high"] * (1 + STOP_BUFFER_PCT)
            risk = stop_price - entry_price
            if risk <= 0:
                continue
            tp_price = entry_price - risk * config.TP_RR_RATIO
        else:
            stop_price = sweep_bar["low"] * (1 - STOP_BUFFER_PCT)
            risk = entry_price - stop_price
            if risk <= 0:
                continue
            tp_price = entry_price + risk * config.TP_RR_RATIO

        setups.append(TradeSetup(
            symbol=symbol, strategy="v2_liquidity_swift", direction=direction,
            signal_bar_pos=trigger_pos, signal_datetime=bar["datetime"],
            entry_price_target=entry_price, stop_price=stop_price, take_profit_price=tp_price,
            valid_until_pos=min(trigger_pos + SETUP_VALIDITY_BARS, len(df_entry) - 1),
            is_limit=False,  # entra a mercado al cierre de la vela
        ))

    return setups
