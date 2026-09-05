"""
Patrones de velas japonesas -- agregado 2026-08-25 a pedido del usuario, a
partir de la lámina de referencia que compartió ("Patrones de Velas
Japonesas"), para afinar la entrada de strategy_v9_bb_rsi_confluence.py (y
sucesoras) por encima del rebote de Bollinger 1h + RSI 4h que ya funciona
como ancla direccional.

No se implementa TODA la lámina: solo los patrones que geométricamente
encajan con el tipo de evento que ya usamos (una reversión puntual, de 1 a 3
velas, en el extremo de un movimiento) -- justo lo que la lámina llama
"Individuales", "Dobles" y "Triples" del lado alcista/bajista. Se deja
afuera el bloque "Confirmaciones" (Three Inside/Outside Up/Down) porque
requiere 3 velas + una tendencia previa marcada, y ya tenemos ADX/EMA para
eso si hiciera falta más adelante -- no hay necesidad de duplicarlo acá.

Todo vectorizado con pandas (sin loops fila por fila para las condiciones
booleanas -- el único loop es para armar el string legible de auditoría) y
sin look-ahead: cada patrón solo usa la vela actual y velas ANTERIORES
(pandas .shift(N) con N positivo).

Convención de salida de add_all_candlestick_patterns:
  - candle_bull_pattern: True si CUALQUIERA de los patrones de 2-3 velas
    alcistas disparó en esa vela (Envolvente, Harami, Piercing, Tweezer
    Bottom, Morning Star).
  - candle_bear_pattern: True si CUALQUIERA de los bajistas disparó
    (Envolvente, Harami, Dark Cloud Cover, Tweezer Top, Evening Star).
  - candle_pattern_names: string con los nombres que dispararon (auditoría).
  - patt_hammer_shape / patt_star_shape: la FORMA geométrica de Martillo /
    Estrella fugaz (cuerpo chico + una mecha larga). Estas dos son
    ambiguas por sí solas -- Martillo (alcista) y Hombre colgado (bajista)
    son la MISMA vela; Estrella fugaz (bajista) e Inverted Hammer (alcista)
    también. Quién las llame decide la dirección combinándolas con el
    contexto (acá: si coincide con bb_reclaim_bull o bb_reclaim_bear).
"""
import numpy as np
import pandas as pd

SMALL_BODY_FRAC = 0.3       # "cuerpo pequeño" = |body| <= 0.3 * rango de la vela
LONG_WICK_MULT = 2.0        # "mecha larga" = mecha >= 2x el cuerpo
NEAR_ZERO_WICK_FRAC = 0.3   # "mecha chica del otro lado" <= 0.3x la mecha larga
TWEEZER_TOL_FRAC = 0.001    # tolerancia entre extremos para "empate" (0.1% del precio)


def _basic_geometry(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["_body"] = df["close"] - df["open"]
    df["_body_abs"] = df["_body"].abs()
    df["_range"] = (df["high"] - df["low"]).replace(0, np.nan)
    df["_upper_wick"] = df["high"] - df[["open", "close"]].max(axis=1)
    df["_lower_wick"] = df[["open", "close"]].min(axis=1) - df["low"]
    df["_is_bull"] = df["close"] > df["open"]
    df["_is_bear"] = df["close"] < df["open"]
    return df


def detect_single_candle_patterns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Lámina, fila "PATRONES DE VELAS INDIVIDUALES": Hammer/Hanging Man
    (cuerpo chico arriba, mecha inferior larga, mecha superior casi nula) e
    Inverted Hammer/Shooting Star (cuerpo chico abajo, mecha superior
    larga, mecha inferior casi nula). Geométricamente cada par es la misma
    vela -- la dirección se resuelve afuera de esta función.
    """
    df = _basic_geometry(df)
    body_abs, range_ = df["_body_abs"], df["_range"]

    long_lower = (df["_lower_wick"] >= LONG_WICK_MULT * body_abs.clip(lower=1e-12)) & \
                 (df["_upper_wick"] <= NEAR_ZERO_WICK_FRAC * df["_lower_wick"].clip(lower=1e-12))
    long_upper = (df["_upper_wick"] >= LONG_WICK_MULT * body_abs.clip(lower=1e-12)) & \
                 (df["_lower_wick"] <= NEAR_ZERO_WICK_FRAC * df["_upper_wick"].clip(lower=1e-12))
    small_body = body_abs <= SMALL_BODY_FRAC * range_

    df["patt_hammer_shape"] = (long_lower & small_body).fillna(False)
    df["patt_star_shape"] = (long_upper & small_body).fillna(False)
    return df


def detect_two_candle_patterns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Lámina, fila "PATRONES DE VELAS DOBLES": Envolvente, Harami, Piercing
    Line / Dark Cloud Cover, Tweezer Bottom/Top. Todas comparan la vela
    actual contra la ANTERIOR (.shift(1)) -- sin look-ahead.
    """
    df = _basic_geometry(df)
    p_open, p_close = df["open"].shift(1), df["close"].shift(1)
    p_high, p_low = df["high"].shift(1), df["low"].shift(1)
    p_is_bull = df["_is_bull"].shift(1).fillna(False).astype(bool)
    p_is_bear = df["_is_bear"].shift(1).fillna(False).astype(bool)

    o, c = df["open"], df["close"]

    # Envolvente alcista / bajista
    df["patt_engulfing_bull"] = (p_is_bear & df["_is_bull"] & (o <= p_close) & (c >= p_open)).fillna(False)
    df["patt_engulfing_bear"] = (p_is_bull & df["_is_bear"] & (o >= p_close) & (c <= p_open)).fillna(False)

    # Harami alcista / bajista (cuerpo actual contenido dentro del cuerpo previo)
    prev_body_hi = pd.concat([p_open, p_close], axis=1).max(axis=1)
    prev_body_lo = pd.concat([p_open, p_close], axis=1).min(axis=1)
    contained = (o <= prev_body_hi) & (o >= prev_body_lo) & (c <= prev_body_hi) & (c >= prev_body_lo)
    df["patt_harami_bull"] = (p_is_bear & df["_is_bull"] & contained).fillna(False)
    df["patt_harami_bear"] = (p_is_bull & df["_is_bear"] & contained).fillna(False)

    # Piercing Line (alcista) / Dark Cloud Cover (bajista)
    prev_mid = (p_open + p_close) / 2
    df["patt_piercing_line"] = (
        p_is_bear & df["_is_bull"] & (o < p_close) & (c > prev_mid) & (c < p_open)
    ).fillna(False)
    df["patt_dark_cloud_cover"] = (
        p_is_bull & df["_is_bear"] & (o > p_close) & (c < prev_mid) & (c > p_open)
    ).fillna(False)

    # Tweezer Bottom / Top (extremos casi iguales entre las dos velas)
    tol = df["close"] * TWEEZER_TOL_FRAC
    df["patt_tweezer_bottom"] = (((df["low"] - p_low).abs() <= tol) & df["_is_bull"]).fillna(False)
    df["patt_tweezer_top"] = (((df["high"] - p_high).abs() <= tol) & df["_is_bear"]).fillna(False)

    return df


def detect_three_candle_patterns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Lámina, fila "PATRONES DE VELAS TRIPLES": Morning Star / Evening Star.
    3 velas: [i-2] impulso fuerte, [i-1] vela chica ("estrella"), [i] vela
    de confirmación que recupera más de la mitad del cuerpo de [i-2].
    """
    df = _basic_geometry(df)
    b2_open, b2_close = df["open"].shift(2), df["close"].shift(2)
    b2_body = df["_body_abs"].shift(2)
    b2_is_bear = (df["close"].shift(2) < df["open"].shift(2)).fillna(False)
    b2_is_bull = (df["close"].shift(2) > df["open"].shift(2)).fillna(False)
    range2 = df["_range"].shift(2)
    star_small = (df["_body_abs"].shift(1) <= SMALL_BODY_FRAC * df["_range"].shift(1)).fillna(False)
    b2_mid = (b2_open + b2_close) / 2

    df["patt_morning_star"] = (
        b2_is_bear & (b2_body >= SMALL_BODY_FRAC * range2) & star_small &
        df["_is_bull"] & (df["close"] > b2_mid)
    ).fillna(False)
    df["patt_evening_star"] = (
        b2_is_bull & (b2_body >= SMALL_BODY_FRAC * range2) & star_small &
        df["_is_bear"] & (df["close"] < b2_mid)
    ).fillna(False)

    return df


def add_all_candlestick_patterns(df: pd.DataFrame) -> pd.DataFrame:
    df = detect_single_candle_patterns(df)
    df = detect_two_candle_patterns(df)
    df = detect_three_candle_patterns(df)

    bull_cols = ["patt_engulfing_bull", "patt_harami_bull", "patt_piercing_line",
                 "patt_tweezer_bottom", "patt_morning_star"]
    bear_cols = ["patt_engulfing_bear", "patt_harami_bear", "patt_dark_cloud_cover",
                 "patt_tweezer_top", "patt_evening_star"]

    df["candle_bull_pattern"] = df[bull_cols].any(axis=1)
    df["candle_bear_pattern"] = df[bear_cols].any(axis=1)

    all_cols = bull_cols + bear_cols
    short_names = [c.replace("patt_", "") for c in all_cols]
    mat = df[all_cols].to_numpy()
    names = [",".join(n for n, hit in zip(short_names, row) if hit) for row in mat]
    df["candle_pattern_names"] = names

    df = df.drop(columns=[c for c in df.columns if c.startswith("_")])
    return df
