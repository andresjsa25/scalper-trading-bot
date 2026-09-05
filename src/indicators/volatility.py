"""ATR y clasificación de régimen de volatilidad (normal / extrema), sin look-ahead."""
import numpy as np
import pandas as pd

REGIME_WINDOW_BARS = 720   # ~30 días en 1h -- ventana móvil para el umbral de percentil
REGIME_PERCENTILE = 70     # ATR > percentil 70 de la ventana móvil -> régimen "extremo"


def add_atr(df: pd.DataFrame, period: int = 14, col_name: str = "atr") -> pd.DataFrame:
    df = df.copy()
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat([
        (high - low).abs(), (high - prev_close).abs(), (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    df[col_name] = tr.rolling(period, min_periods=period).mean()
    return df


def classify_volatility_regime(df: pd.DataFrame, atr_col: str = "atr",
                                window_bars: int = REGIME_WINDOW_BARS,
                                percentile: float = REGIME_PERCENTILE) -> pd.Series:
    """
    Régimen "extremo" si el ATR actual supera el percentil `percentile` de
    los últimos `window_bars` (el umbral se calcula con .shift(1) para no
    usar la propia vela en su umbral -- sin look-ahead). Antes de tener
    ventana suficiente, régimen "normal" por defecto.
    """
    threshold = df[atr_col].rolling(window_bars, min_periods=100).quantile(percentile / 100).shift(1)
    regime = pd.Series("normal", index=df.index)
    regime[df[atr_col] > threshold] = "extreme"
    return regime


def add_bollinger_bands(df: pd.DataFrame, period: int = 20, num_std: float = 2.0,
                         prefix: str = "bb") -> pd.DataFrame:
    """
    Bandas de Bollinger estándar -- agregadas 2026-08-25 a pedido del
    usuario para strategy_v7_confluence.py. Se usan ahí como filtro de
    "extensión": no tomar una señal de entrada si el precio ya está muy
    por fuera de la banda en la dirección del trade (evita perseguir un
    movimiento que ya se agotó), no como estrategia de reversión a la media
    por sí sola.
    """
    df = df.copy()
    mid = df["close"].rolling(period, min_periods=period).mean()
    std = df["close"].rolling(period, min_periods=period).std()

    df[f"{prefix}_mid"] = mid
    df[f"{prefix}_upper"] = mid + num_std * std
    df[f"{prefix}_lower"] = mid - num_std * std
    return df


def recent_band_touch(df: pd.DataFrame, band_col: str, side: str, lookback: int = 5) -> pd.Series:
    """
    Agregada 2026-08-25 para strategy_v8_rsi_confluence.py: '¿el precio
    tocó o superó la banda en las últimas `lookback` velas (incluida la
    actual)?' -- confirma que el movimiento que el RSI está marcando como
    agotado realmente fue una extensión visible, no un vaivén chico.
    side='above' mira el máximo de la vela contra band_col (para banda
    superior); side='below' mira el mínimo contra band_col (para banda
    inferior). Ventana MÓVIL HACIA ATRÁS (pandas .rolling por defecto),
    sin look-ahead: cada vela solo mira velas anteriores + ella misma.
    """
    if side == "above":
        touched = df["high"] >= df[band_col]
    else:
        touched = df["low"] <= df[band_col]
    return touched.rolling(lookback, min_periods=1).max().astype(bool)


def detect_bb_reclaim(df: pd.DataFrame, prefix: str = "bb") -> pd.DataFrame:
    """
    Agregada 2026-08-25 para el research_indicator_confluence_scan.py:
    evento de "rebote" de banda -- la vela ANTERIOR tocó o superó la banda
    (mecha), y la vela ACTUAL cierra de vuelta adentro. Es la versión
    'evento' (dispara en una vela puntual) de la banda de Bollinger, para
    poder tratarla como ancla igual que un cruce de MACD o una salida de
    RSI de zona extrema -- antes solo existía como filtro de estado
    (recent_band_touch), no como gatillo puntual.
    """
    df = df.copy()
    prev_low, prev_high = df["low"].shift(1), df["high"].shift(1)
    prev_lower, prev_upper = df[f"{prefix}_lower"].shift(1), df[f"{prefix}_upper"].shift(1)

    df[f"{prefix}_reclaim_bull"] = (prev_low <= prev_lower) & (df["close"] > df[f"{prefix}_lower"])
    df[f"{prefix}_reclaim_bear"] = (prev_high >= prev_upper) & (df["close"] < df[f"{prefix}_upper"])
    return df
