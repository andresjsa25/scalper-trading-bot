"""
Patrones de vela para V5 (retroceso de Fibonacci): martillo, estrella
fugaz, pinzas y harami. Misma definición técnica ya validada en
fibo-reversal-bot/src/indicators/candle_patterns.py, portada acá porque
es un proyecto separado.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


def _body(df):
    return (df["close"] - df["open"]).abs()


def _range(df):
    return df["high"] - df["low"]


def _upper_wick(df):
    return df["high"] - df[["open", "close"]].max(axis=1)


def _lower_wick(df):
    return df[["open", "close"]].min(axis=1) - df["low"]


def is_hammer(df: pd.DataFrame) -> pd.Series:
    body = _body(df)
    rng = _range(df).replace(0, np.nan)
    lower_wick = _lower_wick(df)
    upper_wick = _upper_wick(df)
    body_nonzero = body.replace(0, np.nan)
    cond = (
        (lower_wick >= config.HAMMER_WICK_TO_BODY_RATIO * body_nonzero)
        & (upper_wick <= config.HAMMER_OPPOSITE_WICK_MAX_RATIO * rng)
    )
    return cond.fillna(False)


def is_shooting_star(df: pd.DataFrame) -> pd.Series:
    body = _body(df)
    rng = _range(df).replace(0, np.nan)
    lower_wick = _lower_wick(df)
    upper_wick = _upper_wick(df)
    body_nonzero = body.replace(0, np.nan)
    cond = (
        (upper_wick >= config.HAMMER_WICK_TO_BODY_RATIO * body_nonzero)
        & (lower_wick <= config.HAMMER_OPPOSITE_WICK_MAX_RATIO * rng)
    )
    return cond.fillna(False)


def is_bullish_harami(df: pd.DataFrame) -> pd.Series:
    prev_open = df["open"].shift(1)
    prev_close = df["close"].shift(1)
    prev_bearish = prev_close < prev_open
    prev_body_top, prev_body_bottom = prev_open, prev_close
    curr_body_top = df[["open", "close"]].max(axis=1)
    curr_body_bottom = df[["open", "close"]].min(axis=1)
    contained = (curr_body_top <= prev_body_top) & (curr_body_bottom >= prev_body_bottom)
    return (prev_bearish & contained).fillna(False)


def is_bearish_harami(df: pd.DataFrame) -> pd.Series:
    prev_open = df["open"].shift(1)
    prev_close = df["close"].shift(1)
    prev_bullish = prev_close > prev_open
    prev_body_top, prev_body_bottom = prev_close, prev_open
    curr_body_top = df[["open", "close"]].max(axis=1)
    curr_body_bottom = df[["open", "close"]].min(axis=1)
    contained = (curr_body_top <= prev_body_top) & (curr_body_bottom >= prev_body_bottom)
    return (prev_bullish & contained).fillna(False)


def is_tweezer_bottom(df: pd.DataFrame) -> pd.Series:
    low1 = df["low"]
    low0 = df["low"].shift(1)
    tol = df["low"] * config.TWEEZER_HL_TOLERANCE_PCT
    match_2 = (low1 - low0).abs() <= tol
    low_2back = df["low"].shift(2)
    match_3 = match_2 & ((low1 - low_2back).abs() <= tol)
    return (match_2 | match_3).fillna(False)


def is_tweezer_top(df: pd.DataFrame) -> pd.Series:
    high1 = df["high"]
    high0 = df["high"].shift(1)
    tol = df["high"] * config.TWEEZER_HL_TOLERANCE_PCT
    match_2 = (high1 - high0).abs() <= tol
    high_2back = df["high"].shift(2)
    match_3 = match_2 & ((high1 - high_2back).abs() <= tol)
    return (match_2 | match_3).fillna(False)


def add_all_patterns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["pat_hammer"] = is_hammer(df)
    df["pat_shooting_star"] = is_shooting_star(df)
    df["pat_bullish_harami"] = is_bullish_harami(df)
    df["pat_bearish_harami"] = is_bearish_harami(df)
    df["pat_tweezer_bottom"] = is_tweezer_bottom(df)
    df["pat_tweezer_top"] = is_tweezer_top(df)
    df["bullish_reversal_pattern"] = df["pat_hammer"] | df["pat_bullish_harami"] | df["pat_tweezer_bottom"]
    df["bearish_reversal_pattern"] = df["pat_shooting_star"] | df["pat_bearish_harami"] | df["pat_tweezer_top"]
    return df
