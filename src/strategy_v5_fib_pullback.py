"""
Estrategia V5 -- "Retroceso de Fibonacci + gestión de salida escalonada"
(video BITLOBO TRADING, "CURSO FIBONACCI #2").

Confirmado con el usuario (2026-08-04): timeframe 1h(entrada)/4h(contexto)
-- el video recomienda H1/H4 como mínimo, no 15min. Esquema de gestión:
simple (breakeven en 38.2%, cierre total en 61.8%) -- el video no da un
número exacto de reparto de parciales ("depende de cada uno"), así que se
usó el esquema más simple posible, confirmado por el usuario.

Lógica:
  1. En CONTEXTO (4h): se identifican los swings (fractales) y se arman
     los "legs" A->B (impulso). Leg alcista (A=bajo, B=alto) -> zona de
     entrada en LARGO en el retroceso. Leg bajista (A=alto, B=bajo) ->
     zona de entrada en CORTO en el rebote. Zona = 61.8%-78.6% del leg
     (mismo cálculo que fibo-reversal-bot).
  2. En ENTRADA (1h): se espera que el precio toque la zona y forme un
     patrón de reversión (martillo/pinzas/harami para largos; estrella
     fugaz/pinzas/harami para cortos). B' = extremo de reacción (mínimo/
     máximo tocado dentro de la zona hasta el cierre del patrón).
     Entrada A MERCADO al open de la vela siguiente al cierre del patrón.
  3. Stop más allá del 88.6% del leg de entrada.
  4. Gestión de salida: se re-dibuja Fibonacci con (B, B') y se calculan
     23.6/38.2/50/61.8/78.6%. Al tocar el 38.2%, el stop sube a punto de
     entrada (breakeven). TP final en el 61.8%.
"""
import os
import sys
from dataclasses import dataclass

import pandas as pd

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "indicators"))
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from indicators.liquidity import find_raw_fractals, build_zigzag_swings
from indicators.candle_patterns import add_all_patterns
from indicators.fibonacci import compute_entry_zone, compute_exit_levels

ZONE_VALIDITY_BARS = 60     # ~10 días en 1h para que el precio llegue a la zona tras B
PATTERN_SEARCH_BARS = 20    # ~20h para que se forme el patrón una vez el precio está en zona
SETUP_VALIDITY_BARS = 200   # ~8 días en 1h para que la gestión de salida se resuelva
STOP_BUFFER_PCT = 0.001
MIN_STOP_DISTANCE_PCT = 0.005  # descarta casos degenerados: entrada casi pegada al 88.6%
                                # (stop casi nulo -> R:R absurdo, ej. 1:200, no es un trade real)
MAX_RR_RATIO = 10.0             # tope de sanidad adicional sobre el R:R implícito


@dataclass
class FibPullbackSetup:
    symbol: str
    direction: str              # 'long' / 'short'
    a_price: float               # swing original (B en el video, el "más alto/bajo" de referencia)
    reaction_price: float        # B' -- extremo de reacción (entrada)
    signal_bar_pos: int
    signal_datetime: pd.Timestamp
    entry_price_target: float
    stop_price: float
    breakeven_trigger_price: float   # nivel 38.2% -- al tocarlo, stop -> breakeven
    take_profit_price: float          # nivel 61.8% -- TP final
    valid_until_pos: int
    risk_pct: float = config.RISK_PER_TRADE_PCT
    strategy: str = "v5_fib_pullback"  # para compatibilidad con live_trading.place_entry_with_sl_tp
    is_limit: bool = False              # V5 siempre entra a mercado
    # -- Campos extra solo para graficar (no los usa el backtest) --
    leg_a_price: float = None        # extremo lejano del impulso original (A del video)
    leg_a_datetime: pd.Timestamp = None
    leg_b_datetime: pd.Timestamp = None  # B del video (mismo valor que a_price acá, con su fecha)
    zone_upper: float = None         # borde superior de la zona de entrada (61.8%/78.6%)
    zone_lower: float = None
    zone_886: float = None           # nivel 88.6%, referencia del stop
    zone_touch_datetime: pd.Timestamp = None
    pattern_datetime: pd.Timestamp = None


def _compute_legs(df_context: pd.DataFrame, min_swing_percentile: float = 0):
    df_context = find_raw_fractals(df_context.copy(), n=2)
    swings = build_zigzag_swings(df_context).sort_values("pos").reset_index(drop=True)
    legs = []
    for i in range(len(swings) - 1):
        a, b = swings.iloc[i], swings.iloc[i + 1]
        direction = "up" if b["type"] == "high" else "down"
        pct_move = abs(b["price"] - a["price"]) / a["price"] * 100
        legs.append({
            "a_price": a["price"], "a_pos": int(a["pos"]), "a_dt": a["datetime"],
            "b_price": b["price"], "b_pos": int(b["pos"]), "b_dt": b["datetime"],
            "direction": direction, "pct_move": pct_move,
        })

    if min_swing_percentile > 0 and len(legs) >= 10:
        import numpy as np
        threshold = np.percentile([leg["pct_move"] for leg in legs], min_swing_percentile)
        legs = [leg for leg in legs if leg["pct_move"] >= threshold]

    return legs


def generate_setups(symbol: str, df_context: pd.DataFrame, df_entry: pd.DataFrame,
                     min_swing_percentile: float = 0, min_rr_ratio: float = 0) -> list:
    legs = _compute_legs(df_context, min_swing_percentile)
    df_entry = add_all_patterns(df_entry.copy())
    entry_datetimes = df_entry["datetime"]

    setups = []
    for leg in legs:
        direction = "long" if leg["direction"] == "up" else "short"
        zone = compute_entry_zone(leg["a_price"], leg["b_price"], leg["direction"])

        entry_start_idx = int(entry_datetimes.searchsorted(leg["b_dt"]))
        if entry_start_idx >= len(df_entry):
            continue

        # 1) esperar a que el precio entre en la zona 61.8%-78.6%
        zone_touch_pos = None
        search_end = min(entry_start_idx + ZONE_VALIDITY_BARS, len(df_entry) - 1)
        for k in range(entry_start_idx, search_end + 1):
            bar = df_entry.iloc[k]
            if bar["low"] <= zone.zone_upper and bar["high"] >= zone.zone_lower:
                zone_touch_pos = k
                break
        if zone_touch_pos is None:
            continue

        # 2) buscar el patrón de reversión desde que entra en zona
        pattern_col = "bullish_reversal_pattern" if direction == "long" else "bearish_reversal_pattern"
        pattern_pos = None
        pattern_end = min(zone_touch_pos + PATTERN_SEARCH_BARS, len(df_entry) - 1)
        for k in range(zone_touch_pos, pattern_end + 1):
            if df_entry[pattern_col].iloc[k]:
                pattern_pos = k
                break
        if pattern_pos is None:
            continue
        if pattern_pos + 1 >= len(df_entry):
            continue

        # B' = extremo de reacción tocado entre la entrada a zona y el patrón (inclusive)
        window = df_entry.iloc[zone_touch_pos:pattern_pos + 1]
        reaction_price = window["low"].min() if direction == "long" else window["high"].max()

        entry_bar_pos = pattern_pos + 1  # entra a mercado al open de la vela siguiente
        entry_bar = df_entry.iloc[entry_bar_pos]
        entry_price = entry_bar["open"]

        if direction == "long":
            stop_price = zone.level_886 * (1 - STOP_BUFFER_PCT)
            if stop_price >= entry_price:
                continue
            # compute_exit_levels mide "% subido desde el low" -- para largos
            # swing_low=reaction (cerca de la entrada) da directamente el
            # orden correcto: 38.2% queda más cerca de la entrada que 61.8%.
            exit_levels = compute_exit_levels(swing_high=leg["b_price"], swing_low=reaction_price)
            breakeven_trigger_price = exit_levels["level_382"]
            take_profit_price = exit_levels["level_618"]
            # La entrada a mercado (open de la vela siguiente al patrón) puede
            # haber saltado por delante del 38.2% si esa vela abrió con fuerza
            # -- en ese caso el "breakeven trigger" quedaría por debajo de la
            # entrada, sin sentido (el stop saltaría a breakeven antes de que
            # el trade demuestre nada). Se descarta ese setup.
            if breakeven_trigger_price <= entry_price:
                continue
        else:
            stop_price = zone.level_886 * (1 + STOP_BUFFER_PCT)
            if stop_price <= entry_price:
                continue
            # Para cortos, swing_high=reaction (cerca de la entrada) invierte
            # el orden: level_382 de la fórmula queda MÁS LEJOS de la entrada
            # (es 61.8% medido desde reaction hacia abajo) y level_618 queda
            # MÁS CERCA (es 38.2% desde reaction). Se usan cruzados a propósito
            # -- confirmado visualmente contra el gráfico (bug real, corregido
            # el 2026-08-04: antes quedaban invertidos).
            exit_levels = compute_exit_levels(swing_high=reaction_price, swing_low=leg["b_price"])
            breakeven_trigger_price = exit_levels["level_618"]
            take_profit_price = exit_levels["level_382"]
            if breakeven_trigger_price >= entry_price:
                continue

        risk = abs(entry_price - stop_price)
        reward = abs(take_profit_price - entry_price)
        if risk / entry_price < MIN_STOP_DISTANCE_PCT:
            continue  # stop casi pegado a la entrada -- caso degenerado
        rr = reward / risk
        if rr > MAX_RR_RATIO:
            continue  # R:R implícito absurdo -- geometría degenerada del leg
        if rr < min_rr_ratio:
            continue  # exige que el Fibonacci de salida dé un R:R mínimo

        setups.append(FibPullbackSetup(
            symbol=symbol, direction=direction,
            a_price=leg["b_price"], reaction_price=reaction_price,
            signal_bar_pos=entry_bar_pos, signal_datetime=entry_bar["datetime"],
            entry_price_target=entry_price, stop_price=stop_price,
            breakeven_trigger_price=breakeven_trigger_price,
            take_profit_price=take_profit_price,
            valid_until_pos=min(entry_bar_pos + SETUP_VALIDITY_BARS, len(df_entry) - 1),
            leg_a_price=leg["a_price"], leg_a_datetime=leg["a_dt"], leg_b_datetime=leg["b_dt"],
            zone_upper=zone.zone_upper, zone_lower=zone.zone_lower, zone_886=zone.level_886,
            zone_touch_datetime=df_entry.iloc[zone_touch_pos]["datetime"],
            pattern_datetime=df_entry.iloc[pattern_pos]["datetime"],
        ))

    return setups
