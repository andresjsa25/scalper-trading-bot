"""
Estrategia V3 -- "CRT + AMD + Turtle Soup/Breaker" (video Pol Castella).

El video usa 4 temporalidades (semanal -> diario -> 15min -> 4h/entrada).
Este proyecto solo tiene 2 (1h de contexto, 15min de entrada) -- ADAPTACIÓN
MÍA, no está en el video tal cual:
  1. En 1h (hace de "diario"): un BREAKER -- vela que CIERRA (no solo
     mecha) más allá de un swing fractal anterior -- define el sesgo y el
     POI (Point of Interest = el cuerpo de esa vela).
  2. En 15min (hace de "M15/estructura + patrón de entrada"): se espera
     que el precio retroceda al POI, dentro de la ventana de sesión, y
     ahí se busca un Turtle Soup sobre un rango de acumulación reciente
     (esto junta en un solo patrón las dos ramas que el video separa:
     "si hay rango -> turtle soup + breaker" / "si no hay rango -> AMD",
     porque el rango + turtle soup YA implica acumulación-manipulación).

Gestión: SL más allá de la mecha del Turtle Soup, TP = config.TP_RR_RATIO.
"""
import os
import sys

import pandas as pd

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "indicators"))
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from indicators.liquidity import find_raw_fractals, build_zigzag_swings, detect_liquidity_sweeps
from indicators.patterns import detect_range, detect_turtle_soup
from session_filter import in_session
from backtest import TradeSetup

POI_RETURN_WINDOW_BARS = 64   # ~16h en 15min para que el precio retroceda al POI del breaker
SOUP_SEARCH_WINDOW_BARS = 32  # ~8h en 15min para que aparezca el Turtle Soup una vez en el POI
SETUP_VALIDITY_BARS = 48
STOP_BUFFER_PCT = 0.0005


def prepare(df_context: pd.DataFrame, df_entry: pd.DataFrame):
    df_context = find_raw_fractals(df_context.copy(), n=2)
    context_swings = build_zigzag_swings(df_context)
    context_sweeps = detect_liquidity_sweeps(df_context, context_swings)

    df_entry = detect_range(df_entry.copy())
    df_entry = detect_turtle_soup(df_entry)
    return df_context, context_sweeps, df_entry


def generate_setups(symbol: str, df_context: pd.DataFrame, df_entry: pd.DataFrame) -> list:
    df_context, context_sweeps, df_entry = prepare(df_context, df_entry)
    setups = []
    entry_datetimes = df_entry["datetime"]

    for _, sweep in context_sweeps.sort_values("pos").iterrows():
        pos = int(sweep["pos"])
        sweep_type = sweep["swing_type"]  # 'high' barrido -> breaker bajista; 'low' -> alcista
        bar = df_context.iloc[pos]

        # Breaker: exige CIERRE más allá del nivel (no solo mecha) -- más estricto que un sweep simple
        if sweep_type == "high" and bar["close"] <= sweep["level_price"]:
            continue
        if sweep_type == "low" and bar["close"] >= sweep["level_price"]:
            continue

        # Sesgo: breaker bajista (rompe un alto) -> luego busco ventas al retroceso; y viceversa
        direction = "short" if sweep_type == "high" else "long"
        poi_top = max(bar["open"], bar["close"])
        poi_bottom = min(bar["open"], bar["close"])

        sweep_dt = bar["datetime"]
        entry_start_idx = int(entry_datetimes.searchsorted(sweep_dt))
        if entry_start_idx >= len(df_entry):
            continue

        # Esperar retroceso al POI dentro de la ventana
        poi_touch_pos = None
        search_end = min(entry_start_idx + POI_RETURN_WINDOW_BARS, len(df_entry) - 1)
        for k in range(entry_start_idx, search_end + 1):
            b = df_entry.iloc[k]
            if b["low"] <= poi_top and b["high"] >= poi_bottom:
                poi_touch_pos = k
                break
        if poi_touch_pos is None:
            continue

        # Buscar Turtle Soup a partir de ahí, dentro de sesión
        soup_col = "turtle_soup_bear" if direction == "short" else "turtle_soup_bull"
        trigger_pos = None
        soup_end = min(poi_touch_pos + SOUP_SEARCH_WINDOW_BARS, len(df_entry) - 1)
        for k in range(poi_touch_pos, soup_end + 1):
            if not df_entry[soup_col].iloc[k]:
                continue
            if not in_session(df_entry.iloc[k]["datetime"]):
                continue
            trigger_pos = k
            break
        if trigger_pos is None:
            continue

        tbar = df_entry.iloc[trigger_pos]
        entry_price = tbar["close"]

        if direction == "short":
            stop_price = tbar["high"] * (1 + STOP_BUFFER_PCT)
            risk = stop_price - entry_price
            if risk <= 0:
                continue
            tp_price = entry_price - risk * config.TP_RR_RATIO
        else:
            stop_price = tbar["low"] * (1 - STOP_BUFFER_PCT)
            risk = entry_price - stop_price
            if risk <= 0:
                continue
            tp_price = entry_price + risk * config.TP_RR_RATIO

        setups.append(TradeSetup(
            symbol=symbol, strategy="v3_crt", direction=direction,
            signal_bar_pos=trigger_pos, signal_datetime=tbar["datetime"],
            entry_price_target=entry_price, stop_price=stop_price, take_profit_price=tp_price,
            valid_until_pos=min(trigger_pos + SETUP_VALIDITY_BARS, len(df_entry) - 1),
            is_limit=False,
        ))

    return setups
