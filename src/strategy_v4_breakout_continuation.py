"""
Estrategia V4 -- "Ruptura + continuación" (diseño propio, no de un video).

Lógica inversa a V1: en vez de asumir que un barrido de liquidez revierte,
asume que un CIERRE (no mecha) más allá de un swing relevante es una
ruptura real que va a CONTINUAR -- pensada específicamente para activos
con comportamiento de cascada de liquidaciones / momentum (BTC) donde V1
(reversión) mostró exactamente el patrón contrario al esperado: a mayor
significancia del swing barrido, peor rendía la reversión.

  1. En CONTEXTO (1h): breaker -- una vela que CIERRA más allá de un swing
     (no solo mecha, igual criterio que V3). Cierre por encima de un swing
     alto -> sesgo ALCISTA (continuación); cierre por debajo de un swing
     bajo -> sesgo BAJISTA.
  2. En ENTRADA (15min): se espera que el precio retroceda a "retestear"
     el nivel roto (ahora soporte/resistencia), dentro de sesión, y ahí
     se busca una vela envolvente con cuerpo a favor de la continuación
     (mismo patrón ya validado visualmente en V2).
  3. Stop más allá del nivel roto (si lo pierde, la ruptura queda
     invalidada). TP = config.TP_RR_RATIO.
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
from indicators.patterns import detect_engulfing
from indicators.trend import add_ema, combined_trend_filter
from session_filter import in_session
from backtest import TradeSetup

RETEST_WINDOW_BARS = 64        # ~16h en 15min para que el precio retroceda a retestear el nivel roto
ENGULFING_SEARCH_WINDOW = 32   # ~8h en 15min para que aparezca la envolvente en el retest
SETUP_VALIDITY_BARS = 48
STOP_BUFFER_PCT = 0.001
MIN_SWING_PERCENTILE = 0
TREND_EMA_PERIOD = 100
USE_TREND_FILTER = False


def prepare(df_context: pd.DataFrame, df_entry: pd.DataFrame, min_swing_percentile: float = MIN_SWING_PERCENTILE):
    df_context = find_raw_fractals(df_context.copy(), n=2)
    context_swings = build_zigzag_swings(df_context)
    context_sweeps = detect_liquidity_sweeps(df_context, context_swings)

    swings_with_pct = compute_swing_legs_pct(context_swings)
    context_sweeps = filter_sweeps_by_min_swing_pct(context_sweeps, swings_with_pct, min_swing_percentile)

    df_context = add_ema(df_context, TREND_EMA_PERIOD, "ema_trend")
    df_context["trend_bias"] = combined_trend_filter(df_context, context_swings, "ema_trend")

    df_entry = detect_engulfing(df_entry.copy())
    return df_context, context_sweeps, df_entry


def generate_setups(symbol: str, df_context: pd.DataFrame, df_entry: pd.DataFrame,
                     min_swing_percentile: float = MIN_SWING_PERCENTILE,
                     use_trend_filter: bool = USE_TREND_FILTER) -> list:
    df_context, context_sweeps, df_entry = prepare(df_context, df_entry, min_swing_percentile)
    setups = []
    entry_datetimes = df_entry["datetime"]

    for _, sweep in context_sweeps.sort_values("pos").iterrows():
        pos = int(sweep["pos"])
        sweep_type = sweep["swing_type"]
        bar = df_context.iloc[pos]

        # Breaker: exige CIERRE más allá del nivel (ruptura real, no mecha)
        if sweep_type == "high" and bar["close"] <= sweep["level_price"]:
            continue
        if sweep_type == "low" and bar["close"] >= sweep["level_price"]:
            continue

        # Sesgo de CONTINUACIÓN (inverso a V1): ruptura de un alto -> largo;
        # ruptura de un bajo -> corto.
        direction = "long" if sweep_type == "high" else "short"

        if use_trend_filter:
            required_bias = "up" if direction == "long" else "down"
            if df_context["trend_bias"].iloc[pos] != required_bias:
                continue

        broken_level = sweep["level_price"]
        sweep_dt = bar["datetime"]
        entry_start_idx = int(entry_datetimes.searchsorted(sweep_dt))
        if entry_start_idx >= len(df_entry):
            continue

        # Esperar el retest del nivel roto
        retest_pos = None
        retest_end = min(entry_start_idx + RETEST_WINDOW_BARS, len(df_entry) - 1)
        for k in range(entry_start_idx, retest_end + 1):
            b = df_entry.iloc[k]
            if b["low"] <= broken_level <= b["high"]:
                retest_pos = k
                break
        if retest_pos is None:
            continue

        # Buscar la envolvente de continuación a partir del retest, en sesión
        engulf_col = "engulfing_bull" if direction == "long" else "engulfing_bear"
        trigger_pos = None
        engulf_end = min(retest_pos + ENGULFING_SEARCH_WINDOW, len(df_entry) - 1)
        for k in range(retest_pos, engulf_end + 1):
            if not df_entry[engulf_col].iloc[k]:
                continue
            if not in_session(df_entry.iloc[k]["datetime"]):
                continue
            trigger_pos = k
            break
        if trigger_pos is None:
            continue

        tbar = df_entry.iloc[trigger_pos]
        entry_price = tbar["close"]

        # Stop más allá del nivel roto -- si lo vuelve a perder, la ruptura
        # queda invalidada.
        if direction == "long":
            stop_price = broken_level * (1 - STOP_BUFFER_PCT)
            risk = entry_price - stop_price
            if risk <= 0:
                continue
            tp_price = entry_price + risk * config.TP_RR_RATIO
        else:
            stop_price = broken_level * (1 + STOP_BUFFER_PCT)
            risk = stop_price - entry_price
            if risk <= 0:
                continue
            tp_price = entry_price - risk * config.TP_RR_RATIO

        setups.append(TradeSetup(
            symbol=symbol, strategy="v4_breakout_continuation", direction=direction,
            signal_bar_pos=trigger_pos, signal_datetime=tbar["datetime"],
            entry_price_target=entry_price, stop_price=stop_price, take_profit_price=tp_price,
            valid_until_pos=min(trigger_pos + SETUP_VALIDITY_BARS, len(df_entry) - 1),
            is_limit=False,
        ))

    return setups
