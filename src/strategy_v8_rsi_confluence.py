"""
Estrategia V8 -- "Confluencia anclada en RSI" (exploratoria, pedida por el
usuario el 2026-08-25 después de que la primera versión -- V7, anclada en
el retest de MACD -- diera profit factor <1 en 8 de 10 activos).

Cambio de enfoque pedido explícitamente por el usuario: "cuando el RSI está
en sobrecompra o sobreventa, podemos buscar qué está pasando con los otros
indicadores en ese momento para ver si podemos predecir el siguiente
movimiento" -- acá el RSI es el ANCLA (dispara la búsqueda de setup) y el
resto de los indicadores (MACD, Bollinger, Volumen, EMA/ADX de 4h) son
confluencias que CONFIRMAN o DESCARTAN esa lectura, no al revés.

Señal de RSI: se usa la SALIDA de la zona extrema (RSI vuelve a cruzar 70
desde arriba, o 30 desde abajo -- indicators/momentum.py: detect_rsi_extreme_exit),
no la entrada a la zona extrema. Motivo: entrar apenas el RSI toca 70/30
significa perseguir un movimiento que puede seguir extendiéndose mucho más
(el mercado puede estar "sobrecomprado" horas); esperar la salida es la
confirmación mínima y más fácil de ver a simple vista de que el extremo ya
quedó atrás.

Dos modos (parámetro `mode`, pensados para poder compararse en el barrido
de calibración -- run_calibrate_v8_rsi_confluence.py):

  - 'reversal': apuesta contraria a la tendencia menor -- el RSI salió de
    un extremo y se espera que el precio revierta, sin importar el sesgo
    de 4h (opcionalmente, si require_adx=True, se EXIGE que el ADX de 4h
    esté POR DEBAJO de ADX_MIN_TREND -- fadear un extremo es más razonable
    si no hay una tendencia fuerte empujando en contra).

  - 'pullback': a favor de la tendencia mayor -- solo se opera si el sesgo
    de 4h (EMA100 + pendiente) apunta en la MISMA dirección del trade, y
    (si require_adx=True) el ADX de 4h confirma que esa tendencia es real.
    El RSI extremo acá no se lee como "el mercado da vuelta", sino como
    "hubo un retroceso dentro de la tendencia y ya se está agotando" --
    la lectura clásica de "comprar barato dentro de una suba".

Confluencias togglables (booleanas, se barren en el calibrador):
  - require_bb_touch: en las últimas BB_TOUCH_LOOKBACK velas, el precio
    tocó o superó la banda de Bollinger del lado del movimiento que se
    está agotando (confirma que fue una extensión real, no un vaivén chico).
  - require_macd_turn: el histograma de MACD ya empezó a girar a favor de
    la nueva dirección en la propia vela de la señal.
  - require_volume: volumen relativo de la vela de señal >= VOLUME_MIN_REL.
  - require_adx: ver arriba (su significado cambia según el modo).

Temporalidades: a diferencia de V7 (4h/1h/15m), acá se simplifica a DOS
(4h para sesgo, 1h para señal Y entrada) por dos razones explícitas: (1)
los CSV de 15m solo tienen ~100 días de historia descargada, mientras que
1h tiene ~1.5 años -- calibrar sobre más historia da resultados más
confiables; (2) el usuario pidió una estrategia "fácil de explicar y
aplicar manualmente" -- dos temporalidades con una sola señal por vela es
más simple de vigilar a mano que tres. Se puede volver a 15m más adelante
si esta lógica muestra una ventaja real y se quiere afinar el timing de entrada.

Gestión: stop = ATR(14) de 1h x ATR_MULT_STOP, TP = riesgo x rr_ratio
(parámetro del calibrador). Entrada a MERCADO en el cierre de la vela de
señal. Aislada de run_live_trading.py / live_trading.py / config.py (salvo
TradeSetup y RISK_PER_TRADE_PCT) -- backtesting puro, NO toca el bot en vivo.
"""
import os
import sys

import pandas as pd

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "indicators"))
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from indicators.trend import add_ema, ema_bias, add_adx
from indicators.momentum import add_rsi, add_macd, add_macd_turning, detect_rsi_extreme_exit
from indicators.volatility import add_bollinger_bands, add_atr, recent_band_touch
from indicators.volume import add_relative_volume
from backtest import TradeSetup
import config

# --- periodos fijos (no se barren en el calibrador, para no explotar la grilla) ---
TREND_EMA_PERIOD = 100
ADX_PERIOD = 14
RSI_PERIOD = 14
MACD_FAST, MACD_SLOW, MACD_SIGNAL = 12, 26, 9
BB_PERIOD, BB_NUM_STD = 20, 2.0
VOLUME_AVG_PERIOD = 20
ATR_PERIOD = 14

# --- umbrales/constantes de la lógica ---
ADX_MIN_TREND = 20            # 'pullback': tendencia real si ADX(4h) >= esto; 'reversal': "sin tendencia fuerte" si ADX(4h) < esto
BB_TOUCH_LOOKBACK = 5          # velas de 1h hacia atrás para el toque de banda
VOLUME_MIN_REL = 1.0
ATR_MULT_STOP = 1.5
SETUP_VALIDITY_BARS_1H = 12    # ~12h -- "entrar y salir rápido", no dejar operaciones colgadas varios días


def prepare_base(df_4h: pd.DataFrame, df_1h: pd.DataFrame):
    """Indicadores que NO dependen de los umbrales de RSI ni de los toggles -- se calculan una sola vez por símbolo."""
    df_4h = df_4h.copy()
    df_4h = add_ema(df_4h, TREND_EMA_PERIOD, "ema_trend")
    df_4h["bias"] = ema_bias(df_4h, "ema_trend")
    df_4h = add_adx(df_4h, ADX_PERIOD, "adx")

    df_1h = df_1h.copy()
    df_1h = add_rsi(df_1h, RSI_PERIOD, "rsi")
    df_1h = add_macd(df_1h, MACD_FAST, MACD_SLOW, MACD_SIGNAL)
    df_1h = add_macd_turning(df_1h)
    df_1h = add_bollinger_bands(df_1h, BB_PERIOD, BB_NUM_STD)
    df_1h = add_relative_volume(df_1h, VOLUME_AVG_PERIOD)
    df_1h = add_atr(df_1h, ATR_PERIOD, "atr")
    df_1h["bb_touch_upper"] = recent_band_touch(df_1h, "bb_upper", "above", BB_TOUCH_LOOKBACK)
    df_1h["bb_touch_lower"] = recent_band_touch(df_1h, "bb_lower", "below", BB_TOUCH_LOOKBACK)

    # sesgo/ADX de 4h proyectados sobre cada vela de 1h (merge_asof = "último valor de 4h conocido a esa hora", sin look-ahead)
    df_1h = pd.merge_asof(
        df_1h.sort_values("datetime"),
        df_4h[["datetime", "bias", "adx"]].rename(columns={"bias": "bias_4h", "adx": "adx_4h"}).sort_values("datetime"),
        on="datetime", direction="backward",
    ).reset_index(drop=True)  # merge_asof no garantiza mantener el índice original -- se fija en 0..n-1
    # explícito para que 'signal_bar_pos' (usado por backtest.simulate_trades vía .iloc) sea correcto.
    return df_4h, df_1h


def generate_setups_from_prepared(symbol: str, df_1h_prepared: pd.DataFrame,
                                   mode: str = "pullback", rsi_ob: float = 70, rsi_os: float = 30,
                                   require_bb_touch: bool = True, require_macd_turn: bool = True,
                                   require_volume: bool = True, require_adx: bool = True,
                                   rr_ratio: float = 2.0) -> list:
    """
    Igual que generate_setups, pero recibe un df_1h YA pasado por
    prepare_base() (RSI/MACD/Bollinger/ADX/volumen/merge con 4h ya
    calculados). Pensada para el calibrador (run_calibrate_v8_rsi_confluence.py),
    que barre cientos de combinaciones de umbrales/toggles por símbolo --
    recalcular todos los indicadores en cada combinación sería carísimo y
    no aporta nada (los indicadores no cambian, solo los umbrales sobre
    ellos). generate_setups() (más abajo) sigue siendo la función normal
    para un uso puntual, para mantener la misma firma que el resto de las
    estrategias del proyecto.
    """
    df = detect_rsi_extreme_exit(df_1h_prepared, "rsi", rsi_ob, rsi_os)

    long_mask = df["rsi_exit_oversold"].copy()
    short_mask = df["rsi_exit_overbought"].copy()

    if require_bb_touch:
        long_mask &= df["bb_touch_lower"]
        short_mask &= df["bb_touch_upper"]
    if require_macd_turn:
        long_mask &= df["macd_turning_up"]
        short_mask &= df["macd_turning_down"]
    if require_volume:
        long_mask &= df["rel_volume"] >= VOLUME_MIN_REL
        short_mask &= df["rel_volume"] >= VOLUME_MIN_REL

    if mode == "pullback":
        long_mask &= df["bias_4h"] == "up"
        short_mask &= df["bias_4h"] == "down"
        if require_adx:
            long_mask &= df["adx_4h"] >= ADX_MIN_TREND
            short_mask &= df["adx_4h"] >= ADX_MIN_TREND
    elif mode == "reversal":
        if require_adx:
            long_mask &= df["adx_4h"] < ADX_MIN_TREND
            short_mask &= df["adx_4h"] < ADX_MIN_TREND
    else:
        raise ValueError(f"mode inválido: {mode!r} (usar 'pullback' o 'reversal')")

    # NaN en columnas de indicadores (arranque de la serie, sin suficiente historia) -> False, no True
    long_mask = long_mask.fillna(False)
    short_mask = short_mask.fillna(False)

    setups = []
    n = len(df)

    for i in df.index[long_mask]:
        bar = df.iloc[i]
        if pd.isna(bar["atr"]) or bar["atr"] <= 0:
            continue
        entry_price = bar["close"]
        stop_price = entry_price - ATR_MULT_STOP * bar["atr"]
        risk = entry_price - stop_price
        if risk <= 0:
            continue
        tp_price = entry_price + risk * rr_ratio
        setups.append(TradeSetup(
            symbol=symbol, strategy=f"v8_{mode}", direction="long",
            signal_bar_pos=i, signal_datetime=bar["datetime"],
            entry_price_target=entry_price, stop_price=stop_price, take_profit_price=tp_price,
            valid_until_pos=min(i + SETUP_VALIDITY_BARS_1H, n - 1),
            risk_pct=config.RISK_PER_TRADE_PCT, is_limit=False,
        ))

    for i in df.index[short_mask]:
        bar = df.iloc[i]
        if pd.isna(bar["atr"]) or bar["atr"] <= 0:
            continue
        entry_price = bar["close"]
        stop_price = entry_price + ATR_MULT_STOP * bar["atr"]
        risk = stop_price - entry_price
        if risk <= 0:
            continue
        tp_price = entry_price - risk * rr_ratio
        setups.append(TradeSetup(
            symbol=symbol, strategy=f"v8_{mode}", direction="short",
            signal_bar_pos=i, signal_datetime=bar["datetime"],
            entry_price_target=entry_price, stop_price=stop_price, take_profit_price=tp_price,
            valid_until_pos=min(i + SETUP_VALIDITY_BARS_1H, n - 1),
            risk_pct=config.RISK_PER_TRADE_PCT, is_limit=False,
        ))

    return setups


def generate_setups(symbol: str, df_4h: pd.DataFrame, df_1h: pd.DataFrame,
                     mode: str = "pullback", rsi_ob: float = 70, rsi_os: float = 30,
                     require_bb_touch: bool = True, require_macd_turn: bool = True,
                     require_volume: bool = True, require_adx: bool = True,
                     rr_ratio: float = 2.0) -> list:
    """Firma estándar del proyecto (símbolo + dataframes crudos) -- para uso puntual, no para el calibrador."""
    _, df_1h_prepared = prepare_base(df_4h, df_1h)
    return generate_setups_from_prepared(
        symbol, df_1h_prepared, mode=mode, rsi_ob=rsi_ob, rsi_os=rsi_os,
        require_bb_touch=require_bb_touch, require_macd_turn=require_macd_turn,
        require_volume=require_volume, require_adx=require_adx, rr_ratio=rr_ratio,
    )
