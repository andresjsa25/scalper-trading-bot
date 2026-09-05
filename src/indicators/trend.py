"""
Filtro de tendencia mayor: EMA100 + estructura de mercado (HH/HL vs LH/LL),
mismo criterio que fibo-reversal-bot/src/indicators/trend.py (ya probado
ahí). Acá se aplica sobre la temporalidad de CONTEXTO (1h) en vez de
diaria, porque este proyecto no tiene una temporalidad más alta que esa.
"""
import pandas as pd


def add_ema(df: pd.DataFrame, period: int, col_name: str = None) -> pd.DataFrame:
    df = df.copy()
    col_name = col_name or f"ema{period}"
    df[col_name] = df["close"].ewm(span=period, adjust=False).mean()
    return df


def ema_simple_bias(df: pd.DataFrame, ema_col: str) -> pd.Series:
    """
    Sesgo simple por EMA (sin exigir pendiente ni estructura): 'up' si el
    cierre está por encima de la EMA, 'down' si está por debajo. Para la
    regla "nunca operar en contra de la EMA10" pedida por el usuario
    (2026-08-04) -- más simple que ema_bias() (que exige pendiente).
    """
    bias = pd.Series("neutral", index=df.index)
    bias[df["close"] > df[ema_col]] = "up"
    bias[df["close"] < df[ema_col]] = "down"
    return bias


def ema_bias(df: pd.DataFrame, ema_col: str) -> pd.Series:
    ema_slope = df[ema_col].diff()
    price_above = df["close"] > df[ema_col]
    price_below = df["close"] < df[ema_col]

    bias = pd.Series("neutral", index=df.index)
    bias[price_above & (ema_slope > 0)] = "up"
    bias[price_below & (ema_slope < 0)] = "down"
    return bias


def market_structure_at_each_bar(df: pd.DataFrame, swings: pd.DataFrame) -> pd.Series:
    """
    O(n) con punteros -- antes filtraba TODOS los swings en cada vela
    (O(n^2)), que con ~13000 velas de contexto (1.5 años en 1h) tardaba
    minutos por símbolo. Mismo resultado, solo más rápido.
    """
    structure = pd.Series("neutral", index=df.index)

    highs = swings[swings["type"] == "high"].reset_index(drop=True)
    lows = swings[swings["type"] == "low"].reset_index(drop=True)

    if len(highs) < 2 or len(lows) < 2:
        return structure

    h_ptr = l_ptr = 0
    last_h = prev_h = last_l = prev_l = None

    for i in range(len(df)):
        while h_ptr < len(highs) and highs.loc[h_ptr, "pos"] <= i:
            prev_h, last_h = last_h, highs.loc[h_ptr, "price"]
            h_ptr += 1
        while l_ptr < len(lows) and lows.loc[l_ptr, "pos"] <= i:
            prev_l, last_l = last_l, lows.loc[l_ptr, "price"]
            l_ptr += 1

        if prev_h is None or prev_l is None:
            continue

        if last_h > prev_h and last_l > prev_l:
            structure.iloc[i] = "up"
        elif last_h < prev_h and last_l < prev_l:
            structure.iloc[i] = "down"

    return structure


def combined_trend_filter(df: pd.DataFrame, swings: pd.DataFrame, ema_col: str) -> pd.Series:
    ema_side = ema_bias(df, ema_col)
    structure_side = market_structure_at_each_bar(df, swings)

    combined = pd.Series("neutral", index=df.index)
    combined[(ema_side == "up") & (structure_side == "up")] = "up"
    combined[(ema_side == "down") & (structure_side == "down")] = "down"
    return combined


def add_adx(df: pd.DataFrame, period: int = 14, col_name: str = "adx") -> pd.DataFrame:
    """
    ADX de Wilder -- agregado 2026-08-25 a pedido del usuario para
    strategy_v7_confluence.py, como filtro de "hay tendencia real detrás
    del movimiento o el mercado está lateral" en la temporalidad de 4h
    (no existía en el proyecto hasta ahora; V1/sanchezzfx usan EMA +
    estructura de swings para lo mismo, no ADX).

    Cálculo estándar (+DM/-DM, TR, suavizado de Wilder = ewm alpha=1/period,
    igual que add_rsi en momentum.py):
    """
    df = df.copy()
    high, low, close = df["high"], df["low"], df["close"]
    prev_high, prev_low, prev_close = high.shift(1), low.shift(1), close.shift(1)

    up_move = high - prev_high
    down_move = prev_low - low

    plus_dm = pd.Series(0.0, index=df.index)
    minus_dm = pd.Series(0.0, index=df.index)
    plus_dm[(up_move > down_move) & (up_move > 0)] = up_move[(up_move > down_move) & (up_move > 0)]
    minus_dm[(down_move > up_move) & (down_move > 0)] = down_move[(down_move > up_move) & (down_move > 0)]

    tr = pd.concat([
        (high - low).abs(), (high - prev_close).abs(), (low - prev_close).abs(),
    ], axis=1).max(axis=1)

    atr_wilder = tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    plus_di = 100 * (plus_dm.ewm(alpha=1 / period, min_periods=period, adjust=False).mean() / atr_wilder)
    minus_di = 100 * (minus_dm.ewm(alpha=1 / period, min_periods=period, adjust=False).mean() / atr_wilder)

    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    df[col_name] = dx.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    return df
