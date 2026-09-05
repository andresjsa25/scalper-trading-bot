"""
Estrategia V10 -- "Rebote de Bollinger 1h + RSI 4h", con dos mejoras que pidió
el usuario sobre V9 (2026-08-25):

  1. rr FIJO en 1:2 (arriesgar 1, buscar ganar 2) -- ya no se barre rr_ratio,
     se calibra el STOP en su lugar, con dos formas de definirlo (stop_mode):

       - "atr":  stop = precio de cierre -/+ ATR_MULT * ATR(14) de 1h.
                 Es lo mismo que V9, pero ahora ATR_MULT se calibra POR
                 SÍMBOLO (igual criterio que V1_LIVE_CONFIG en V1), en vez
                 de usar un valor fijo para los 10 activos.

       - "wick": stop = un poco más allá del extremo de la mecha que generó
                 el rebote (el mínimo/máximo entre la vela que perforó la
                 banda y la vela de cierre de vuelta adentro), con un
                 colchón chico = WICK_BUFFER_ATR_FRAC * ATR(14). Esto ata el
                 stop a la ACCIÓN DEL PRECIO real de la señal (si el precio
                 rompe el extremo de la mecha, la idea del rebote quedó
                 invalidada) en vez de a un múltiplo arbitrario de ATR.

  2. Filtro opcional de patrón de vela (require_pattern): exige que,
     además del rebote de Bollinger + RSI de 4h, la vela de la señal (o el
     par de velas) también forme uno de los patrones de reversión de
     src/indicators/candlestick_patterns.py -- Martillo/Estrella fugaz
     (misma vela del rebote), Envolvente, Harami, Piercing/Dark Cloud,
     Tweezer, o Morning/Evening Star. Se deja como toggle (no fijo en
     True) para poder comparar CON y SIN ese filtro, tal como pidió el
     usuario, en vez de asumir que ayuda.

El ancla direccional (bb_reclaim 1h + rsi_4h > / < 50) es la misma que en
V9 -- ese patrón ya se verificó por separado en
research_indicator_confluence_scan.py (10/10 símbolos, 61-63% hit-rate) y
NO se toca acá; lo único que cambia es cómo se gestiona el riesgo y qué tan
exigente es el filtro de entrada.

Aislada de run_live_trading.py / live_trading.py / config.py (salvo
TradeSetup y RISK_PER_TRADE_PCT) -- backtesting puro, NO toca el bot en vivo.
"""
import os
import sys

import pandas as pd

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "indicators"))
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from indicators.momentum import add_rsi
from indicators.volatility import add_bollinger_bands, detect_bb_reclaim, add_atr
from indicators.candlestick_patterns import add_all_candlestick_patterns
from backtest import TradeSetup
import config

BB_PERIOD, BB_NUM_STD = 20, 2.0
RSI_PERIOD = 14
ATR_PERIOD = 14
RR_RATIO_FIXED = 2.0  # "si arriesgamos 1, buscamos ganar 2" -- ya no se barre, se fija
SETUP_VALIDITY_BARS_1H = 12  # ~12h, igual que V9

DEFAULT_ATR_MULT = 1.5
DEFAULT_WICK_BUFFER_ATR_FRAC = 0.1


def prepare(df_4h: pd.DataFrame, df_1h: pd.DataFrame):
    df_4h = df_4h.copy()
    df_4h = add_rsi(df_4h, RSI_PERIOD, "rsi")

    df_1h = df_1h.copy()
    df_1h = add_bollinger_bands(df_1h, BB_PERIOD, BB_NUM_STD)
    df_1h = detect_bb_reclaim(df_1h)
    df_1h = add_atr(df_1h, ATR_PERIOD, "atr")
    df_1h = add_all_candlestick_patterns(df_1h)

    df_1h = pd.merge_asof(
        df_1h.sort_values("datetime"),
        df_4h[["datetime", "rsi"]].rename(columns={"rsi": "rsi_4h"}).sort_values("datetime"),
        on="datetime", direction="backward",
    ).reset_index(drop=True)

    # patt_hammer_shape / patt_star_shape son ambiguos por sí solos (ver
    # docstring del módulo) -- se resuelven acá combinándolos con la
    # dirección del rebote que ya conocemos en este punto.
    df_1h["candle_bull_final"] = (
        df_1h["candle_bull_pattern"] | (df_1h["patt_hammer_shape"] & df_1h["bb_reclaim_bull"])
    ).fillna(False)
    df_1h["candle_bear_final"] = (
        df_1h["candle_bear_pattern"] | (df_1h["patt_star_shape"] & df_1h["bb_reclaim_bear"])
    ).fillna(False)

    return df_4h, df_1h


def generate_setups_from_prepared(
    symbol: str, df: pd.DataFrame, stop_mode: str = "atr",
    atr_mult: float = DEFAULT_ATR_MULT, wick_buffer_atr_frac: float = DEFAULT_WICK_BUFFER_ATR_FRAC,
    require_pattern: bool = False, rr_ratio: float = RR_RATIO_FIXED,
) -> list:
    long_mask = (df["bb_reclaim_bull"] & (df["rsi_4h"] > 50)).fillna(False)
    short_mask = (df["bb_reclaim_bear"] & (df["rsi_4h"] < 50)).fillna(False)
    if require_pattern:
        long_mask = long_mask & df["candle_bull_final"].fillna(False)
        short_mask = short_mask & df["candle_bear_final"].fillna(False)

    setups = []
    n = len(df)

    for i in df.index[long_mask]:
        if i == 0 or pd.isna(df.at[i, "atr"]) or df.at[i, "atr"] <= 0:
            continue
        bar = df.iloc[i]
        entry_price = bar["close"]
        if stop_mode == "atr":
            stop_price = entry_price - atr_mult * bar["atr"]
        else:  # "wick": más allá del extremo real de la mecha que generó el rebote
            wick_low = min(df.at[i - 1, "low"], bar["low"])
            stop_price = wick_low - wick_buffer_atr_frac * bar["atr"]
        risk = entry_price - stop_price
        if risk <= 0:
            continue
        tp_price = entry_price + risk * rr_ratio
        setups.append(TradeSetup(
            symbol=symbol, strategy="v10_bb_rsi_refined", direction="long",
            signal_bar_pos=i, signal_datetime=bar["datetime"],
            entry_price_target=entry_price, stop_price=stop_price, take_profit_price=tp_price,
            valid_until_pos=min(i + SETUP_VALIDITY_BARS_1H, n - 1),
            risk_pct=config.RISK_PER_TRADE_PCT, is_limit=False,
        ))

    for i in df.index[short_mask]:
        if i == 0 or pd.isna(df.at[i, "atr"]) or df.at[i, "atr"] <= 0:
            continue
        bar = df.iloc[i]
        entry_price = bar["close"]
        if stop_mode == "atr":
            stop_price = entry_price + atr_mult * bar["atr"]
        else:  # "wick"
            wick_high = max(df.at[i - 1, "high"], bar["high"])
            stop_price = wick_high + wick_buffer_atr_frac * bar["atr"]
        risk = stop_price - entry_price
        if risk <= 0:
            continue
        tp_price = entry_price - risk * rr_ratio
        setups.append(TradeSetup(
            symbol=symbol, strategy="v10_bb_rsi_refined", direction="short",
            signal_bar_pos=i, signal_datetime=bar["datetime"],
            entry_price_target=entry_price, stop_price=stop_price, take_profit_price=tp_price,
            valid_until_pos=min(i + SETUP_VALIDITY_BARS_1H, n - 1),
            risk_pct=config.RISK_PER_TRADE_PCT, is_limit=False,
        ))

    return setups


def generate_setups(symbol: str, df_4h: pd.DataFrame, df_1h: pd.DataFrame, **kwargs) -> list:
    _, df = prepare(df_4h, df_1h)
    return generate_setups_from_prepared(symbol, df, **kwargs)
