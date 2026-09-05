"""
Estrategia V1 -- "Sniper de liquidez" (video BELIKETHEALGO).

Lógica (según la transcripción del video):
  1. En la temporalidad de CONTEXTO (1h, equivalente a las 4h del video)
     se ubica el último swing (fractal) alto/bajo. Cuando el precio lo
     "toma" (mecha por encima/debajo), queda marcado un punto de liquidez
     barrido: si barrió un ALTO -> sesgo VENTA; si barrió un BAJO -> sesgo COMPRA.
  2. En la temporalidad de ENTRADA (15min, equivalente al 1min del video)
     se espera un cambio de estructura (CHoCH) en la dirección del sesgo.
  3. Se busca un FVG (desequilibrio de 3 velas) cerca del CHoCH y se
     entra cuando el precio retrocede a mitigar ese FVG (fair value = punto
     medio del hueco).
  4. Solo se opera dentro de la ventana de sesión (Londres/NY, config.SESSION_WINDOWS_UTC).

Los números de ventana (cuántas velas se espera el CHoCH, el FVG, el
relleno) NO los da el video con una cifra exacta -- son mi mejor
traducción a reglas medibles de lo que se explica y muestra en el
ejemplo. Quedan como constantes acá arriba para que se puedan ajustar
fácil si el backtesting no calza con lo esperado.
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
from indicators.patterns import detect_fvg, find_choch_after_sweep
from indicators.trend import add_ema, combined_trend_filter
from indicators.volatility import add_atr, classify_volatility_regime
from session_filter import in_session
from backtest import TradeSetup

CHOCH_LOOKAHEAD_BARS = 48      # ~12h en 15min para que aparezca el CHoCH tras el barrido
FVG_SEARCH_WINDOW = 4          # velas alrededor del CHoCH donde se busca el FVG
FILL_WINDOW_BARS = 24          # ~6h en 15min para que el precio retroceda a mitigar el FVG
SETUP_VALIDITY_BARS = 48       # ~12h en 15min para que la operación se resuelva (SL/TP/time_exit)
STOP_BUFFER_PCT = 0.001        # 0.1% más allá del nivel barrido (mismo criterio que fibo-reversal-bot)
MIN_SWING_PERCENTILE = 0       # 0 = sin filtro; parámetro a calibrar (ver run_sensitivity_v1.py)
TREND_EMA_PERIOD = 100         # EMA de tendencia mayor sobre el contexto (1h) -- mismo criterio que fibo-reversal-bot
USE_TREND_FILTER = False       # por defecto apagado (no cambia el comportamiento ya calibrado); se activa por símbolo
USE_SESSION_FILTER = True      # apagar para XAUT (el video dice que el oro no respeta sesión)
REQUIRE_REGIME = None          # None / 'normal' / 'extreme' -- filtro de régimen de volatilidad (ATR)


def prepare(df_context: pd.DataFrame, df_entry: pd.DataFrame, min_swing_percentile: float = MIN_SWING_PERCENTILE):
    df_context = find_raw_fractals(df_context.copy(), n=2)
    context_swings = build_zigzag_swings(df_context)
    context_sweeps = detect_liquidity_sweeps(df_context, context_swings)

    swings_with_pct = compute_swing_legs_pct(context_swings)
    context_sweeps = filter_sweeps_by_min_swing_pct(context_sweeps, swings_with_pct, min_swing_percentile)

    df_context = add_ema(df_context, TREND_EMA_PERIOD, "ema_trend")
    df_context["trend_bias"] = combined_trend_filter(df_context, context_swings, "ema_trend")
    df_context = add_atr(df_context, period=14, col_name="atr")
    df_context["vol_regime"] = classify_volatility_regime(df_context, atr_col="atr")

    df_entry = find_raw_fractals(df_entry.copy(), n=2)
    entry_swings = build_zigzag_swings(df_entry)
    df_entry = detect_fvg(df_entry)

    return df_context, context_sweeps, df_entry, entry_swings


def generate_setups(symbol: str, df_context: pd.DataFrame, df_entry: pd.DataFrame,
                     min_swing_percentile: float = MIN_SWING_PERCENTILE,
                     use_trend_filter: bool = USE_TREND_FILTER,
                     use_session_filter: bool = USE_SESSION_FILTER,
                     require_regime: str = REQUIRE_REGIME) -> list:
    df_context, context_sweeps, df_entry, entry_swings = prepare(df_context, df_entry, min_swing_percentile)
    setups = []

    entry_datetimes = df_entry["datetime"]

    # Se separa una sola vez por tipo, como arrays de numpy (pos, price) --
    # antes esto se recalculaba (filtro + sort, y encima con acceso .loc
    # escalar) ADENTRO de find_choch_after_sweep en cada barrido. Ver
    # docstring de esa función en indicators/patterns.py para el detalle
    # completo (incluye una segunda optimización, búsqueda binaria del
    # punto de arranque).
    def _swings_arrays(swing_type):
        sub = entry_swings[entry_swings["type"] == swing_type].sort_values("pos")
        return sub["pos"].to_numpy(), sub["price"].to_numpy()

    entry_swings_by_type = {
        "high": _swings_arrays("high"),
        "low": _swings_arrays("low"),
    }

    for _, sweep in context_sweeps.sort_values("pos").iterrows():
        sweep_type = sweep["swing_type"]
        direction = "short" if sweep_type == "high" else "long"
        sweep_level_price = sweep["level_price"]
        sweep_pos = int(sweep["pos"])
        sweep_dt = df_context.iloc[sweep_pos]["datetime"]

        if use_trend_filter:
            # Reversión a favor de la tendencia mayor (mismo criterio que
            # fibo-reversal-bot): barrer un ALTO para vender solo si la
            # tendencia de 1h es bajista (retroceso dentro de una baja);
            # barrer un BAJO para comprar solo si la tendencia es alcista.
            required_bias = "down" if direction == "short" else "up"
            if df_context["trend_bias"].iloc[sweep_pos] != required_bias:
                continue

        if require_regime is not None:
            if df_context["vol_regime"].iloc[sweep_pos] != require_regime:
                continue

        entry_start_idx = int(entry_datetimes.searchsorted(sweep_dt))
        if entry_start_idx >= len(df_entry):
            continue

        choch_pos = find_choch_after_sweep(
            df_entry, entry_start_idx, sweep_type,
            max_lookahead=CHOCH_LOOKAHEAD_BARS, swings_by_type=entry_swings_by_type,
        )
        if choch_pos is None:
            continue

        fvg_col = "fvg_bear" if direction == "short" else "fvg_bull"
        top_col = "fvg_bear_top" if direction == "short" else "fvg_bull_top"
        bottom_col = "fvg_bear_bottom" if direction == "short" else "fvg_bull_bottom"

        fvg_pos = None
        search_end = min(choch_pos + FVG_SEARCH_WINDOW, len(df_entry) - 1)
        for j in range(choch_pos, search_end + 1):
            if df_entry[fvg_col].iloc[j]:
                fvg_pos = j
                break
        if fvg_pos is None:
            continue

        fvg_top = df_entry[top_col].iloc[fvg_pos]
        fvg_bottom = df_entry[bottom_col].iloc[fvg_pos]
        # Entrada en el BORDE del hueco más cercano al precio actual, no en el
        # punto medio -- confirmado visualmente contra el video (min 11:15-11:20):
        # el precio entra apenas toca el borde, no espera a mitigar todo el FVG.
        entry_price = fvg_bottom if direction == "short" else fvg_top

        fill_pos = None
        fill_end = min(fvg_pos + FILL_WINDOW_BARS, len(df_entry) - 1)
        for k in range(fvg_pos, fill_end + 1):
            bar = df_entry.iloc[k]
            if use_session_filter and not in_session(bar["datetime"]):
                continue
            if direction == "short" and bar["low"] <= entry_price <= bar["high"]:
                fill_pos = k
                break
            if direction == "long" and bar["low"] <= entry_price <= bar["high"]:
                fill_pos = k
                break
        if fill_pos is None:
            continue

        # Stop justo más allá del extremo de la VELA 1 del propio FVG (local,
        # ajustado) -- confirmado visualmente contra el video (min 11:20).
        # NO va en el nivel de liquidez original barrido (eso quedaba muy lejos).
        candle1_pos = fvg_pos - 2
        if direction == "short":
            stop_price = df_entry["high"].iloc[candle1_pos] * (1 + STOP_BUFFER_PCT)
            risk = stop_price - entry_price
            if risk <= 0:
                continue
            tp_price = entry_price - risk * config.TP_RR_RATIO
        else:
            stop_price = df_entry["low"].iloc[candle1_pos] * (1 - STOP_BUFFER_PCT)
            risk = entry_price - stop_price
            if risk <= 0:
                continue
            tp_price = entry_price + risk * config.TP_RR_RATIO

        setups.append(TradeSetup(
            symbol=symbol, strategy="v1_sniper", direction=direction,
            signal_bar_pos=fill_pos, signal_datetime=df_entry.iloc[fill_pos]["datetime"],
            entry_price_target=entry_price, stop_price=stop_price, take_profit_price=tp_price,
            valid_until_pos=min(fill_pos + SETUP_VALIDITY_BARS, len(df_entry) - 1),
            is_limit=True,
        ))

    return setups
