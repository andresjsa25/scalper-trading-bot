"""
Estrategia V7 -- "Confluencia de 6 indicadores" (exploratoria, pedida por
el usuario el 2026-08-25 para comparar contra V1, la que corre hoy en vivo).

Origen: el usuario mostró una captura de BTCUSDT en BingX (15min) donde
marcó a mano un cruce de la línea MACD sobre la señal seguido de una
corrección, y dijo (textual): "no sé cómo se usa el MACD pero yo veo que
ese mismo patrón se repite muchas veces acertando los trades" y "muchas
veces en el retest es cuando está la mejor oportunidad para entrar, pero
muchas veces es erróneo". De ahí la idea central: el cruce de MACD +
retest NO se usa solo (admite fallos), se exige que 5 confirmaciones más
estén alineadas al mismo tiempo para filtrar los falsos positivos.

Los 6 indicadores confirmados con el usuario (2026-08-25): RSI, MACD,
Volumen (relativo, ya existía en indicators/volume.py), Bandas de
Bollinger, EMA/estructura de tendencia y ADX.

Jerarquía de temporalidades (confirmada con el usuario): "4h para tener
referencia de la estructura del mercado, 1h y 15min para buscar entradas,
la idea es entrar y salir rápido, no durar mucho tiempo con una posición
abierta" -- de ahí:

  1. 4h = SESGO ESTRUCTURAL (no dispara nada, solo filtra dirección):
     - EMA100 con pendiente (indicators/trend.py: ema_bias) -> 'up'/'down'.
     - ADX(14) >= ADX_MIN_TREND -> confirma que ese sesgo es una tendencia
       real y no un mercado lateral (si no, se descarta el sesgo).

  2. 1h = CONFIRMACIÓN DE MOMENTUM (filtra, tampoco dispara):
     - MACD: la línea debe estar del lado del sesgo 4h (por encima de la
       señal para sesgo alcista, por debajo para bajista) EN ESE MOMENTO
       (no se exige un cruce fresco acá, el cruce fresco se busca en 15m).
     - RSI(14) dentro de una banda que confirma momentum sin estar ya en
       extremo (evita comprar sobrecomprado / vender sobrevendido).

  3. 15m = GATILLO DE ENTRADA (acá sí dispara la operación):
     - Cruce de MACD + RETEST (indicators/momentum.py: find_macd_retest_triggers)
       en la dirección del sesgo -- es la traducción directa del patrón
       que el usuario señaló en su captura.
     - Bandas de Bollinger: el precio NO debe estar ya por fuera de la
       banda en la dirección del trade en la vela del retest (evita
       perseguir un movimiento agotado).
     - Volumen relativo >= VOLUME_MIN_REL en la vela del retest (confirma
       que hubo participación real, no un retest en volumen muerto).

Gestión: stop = ATR(14) de 15m x ATR_MULT_STOP desde el precio de entrada
(estilo scalp, igual de rápido que V1). TP = riesgo x rr_ratio (parámetro
explícito de generate_setups, se barre en el backtest, NO se lee de
config.TP_RR_RATIO -- mismo criterio que strategy_sanchezzfx.py, para no
acoplar este backtest exploratorio a la config del bot en vivo). Entrada
a MERCADO en el cierre de la vela de retest (is_limit=False) -- el propio
retest ya ES el retroceso, no hace falta una orden límite adicional
esperando otro retroceso.

Aislada a propósito de run_live_trading.py / live_trading.py / config.py
(salvo TradeSetup y RISK_PER_TRADE_PCT, sin efectos secundarios) -- pensada
para backtesting puro, igual que sanchezzfx. NO toca el bot en vivo.

Primera versión: los umbrales (ADX_MIN_TREND, bandas de RSI, retrace_frac
del retest, VOLUME_MIN_REL, ATR_MULT_STOP) son puntos de partida
razonables, no calibrados todavía -- se ajustan según lo que diga el
backtesting (run_backtest_v7_confluence.py), mismo criterio que el resto
del proyecto (ver config.py: TP_RR_RATIO).
"""
import os
import sys

import pandas as pd

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "indicators"))
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from indicators.trend import add_ema, ema_bias, add_adx
from indicators.momentum import add_rsi, add_macd, detect_macd_cross, find_macd_retest_triggers
from indicators.volatility import add_bollinger_bands, add_atr
from indicators.volume import add_relative_volume
from backtest import TradeSetup
import config

# --- 4h: sesgo estructural ---
TREND_EMA_PERIOD = 100
ADX_PERIOD = 14
ADX_MIN_TREND = 20          # por debajo se considera mercado lateral (regla de dedo estándar de ADX), se descarta el sesgo

# --- 1h: confirmación de momentum ---
RSI_PERIOD = 14
RSI_LONG_MIN, RSI_LONG_MAX = 50, 75    # momentum alcista confirmado, sin estar ya en sobrecompra extrema
RSI_SHORT_MIN, RSI_SHORT_MAX = 25, 50  # momentum bajista confirmado, sin estar ya en sobreventa extrema

# --- 15m: gatillo ---
MACD_FAST, MACD_SLOW, MACD_SIGNAL = 12, 26, 9
RETEST_RETRACE_FRAC = 0.3        # el histograma retrocede a <=30% de su máximo desde el cruce -> retest
RETEST_MAX_BARS_15M = 20         # ~5h en 15min para que aparezca el retest tras el cruce
BB_PERIOD, BB_NUM_STD = 20, 2.0
VOLUME_AVG_PERIOD = 20
VOLUME_MIN_REL = 1.0              # volumen de la vela >= su propio promedio reciente

# --- Gestión ---
ATR_PERIOD = 14
ATR_MULT_STOP = 1.5
SETUP_VALIDITY_BARS_15M = 32      # ~8h en 15min -- "entrar y salir rápido" (scalp), no dejar operaciones colgadas


def prepare(df_4h: pd.DataFrame, df_1h: pd.DataFrame, df_15m: pd.DataFrame):
    df_4h = df_4h.copy()
    df_4h = add_ema(df_4h, TREND_EMA_PERIOD, "ema_trend")
    df_4h["bias"] = ema_bias(df_4h, "ema_trend")
    df_4h = add_adx(df_4h, ADX_PERIOD, "adx")

    df_1h = df_1h.copy()
    df_1h = add_macd(df_1h, MACD_FAST, MACD_SLOW, MACD_SIGNAL)
    df_1h = add_rsi(df_1h, RSI_PERIOD)

    df_15m = df_15m.copy()
    df_15m = add_macd(df_15m, MACD_FAST, MACD_SLOW, MACD_SIGNAL)
    df_15m = detect_macd_cross(df_15m)
    df_15m = find_macd_retest_triggers(df_15m, retrace_frac=RETEST_RETRACE_FRAC,
                                        max_bars_after_cross=RETEST_MAX_BARS_15M)
    df_15m = add_bollinger_bands(df_15m, BB_PERIOD, BB_NUM_STD)
    df_15m = add_relative_volume(df_15m, VOLUME_AVG_PERIOD)
    df_15m = add_atr(df_15m, ATR_PERIOD, "atr")

    return df_4h, df_1h, df_15m


def generate_setups(symbol: str, df_4h: pd.DataFrame, df_1h: pd.DataFrame, df_15m: pd.DataFrame,
                     rr_ratio: float = 2.0) -> list:
    df_4h, df_1h, df_15m = prepare(df_4h, df_1h, df_15m)
    setups = []

    h4_datetimes = df_4h["datetime"]
    h1_datetimes = df_1h["datetime"]

    for i in range(len(df_15m)):
        bar = df_15m.iloc[i]

        if bar["macd_retest_long"]:
            direction = "long"
        elif bar["macd_retest_short"]:
            direction = "short"
        else:
            continue

        dt = bar["datetime"]

        # --- 4h: sesgo estructural ---
        h4_pos = int(h4_datetimes.searchsorted(dt, side="right")) - 1
        if h4_pos < 0:
            continue
        h4_bar = df_4h.iloc[h4_pos]
        required_bias = "up" if direction == "long" else "down"
        if h4_bar["bias"] != required_bias:
            continue
        if pd.isna(h4_bar["adx"]) or h4_bar["adx"] < ADX_MIN_TREND:
            continue

        # --- 1h: confirmación de momentum ---
        h1_pos = int(h1_datetimes.searchsorted(dt, side="right")) - 1
        if h1_pos < 0:
            continue
        h1_bar = df_1h.iloc[h1_pos]
        if pd.isna(h1_bar["macd_line"]) or pd.isna(h1_bar["rsi"]):
            continue
        if direction == "long":
            if not (h1_bar["macd_line"] > h1_bar["macd_signal"]):
                continue
            if not (RSI_LONG_MIN <= h1_bar["rsi"] <= RSI_LONG_MAX):
                continue
        else:
            if not (h1_bar["macd_line"] < h1_bar["macd_signal"]):
                continue
            if not (RSI_SHORT_MIN <= h1_bar["rsi"] <= RSI_SHORT_MAX):
                continue

        # --- 15m: filtros adicionales en la propia vela del gatillo ---
        if pd.isna(bar["bb_upper"]) or pd.isna(bar["rel_volume"]) or pd.isna(bar["atr"]):
            continue
        if direction == "long" and bar["close"] >= bar["bb_upper"]:
            continue  # ya extendido por fuera de la banda -- no perseguir
        if direction == "short" and bar["close"] <= bar["bb_lower"]:
            continue
        if bar["rel_volume"] < VOLUME_MIN_REL:
            continue

        entry_price = bar["close"]
        atr = bar["atr"]
        if direction == "long":
            stop_price = entry_price - ATR_MULT_STOP * atr
            risk = entry_price - stop_price
            if risk <= 0:
                continue
            tp_price = entry_price + risk * rr_ratio
        else:
            stop_price = entry_price + ATR_MULT_STOP * atr
            risk = stop_price - entry_price
            if risk <= 0:
                continue
            tp_price = entry_price - risk * rr_ratio

        setups.append(TradeSetup(
            symbol=symbol, strategy="v7_confluence", direction=direction,
            signal_bar_pos=i, signal_datetime=dt,
            entry_price_target=entry_price, stop_price=stop_price, take_profit_price=tp_price,
            valid_until_pos=min(i + SETUP_VALIDITY_BARS_15M, len(df_15m) - 1),
            risk_pct=config.RISK_PER_TRADE_PCT, is_limit=False,
        ))

    return setups
