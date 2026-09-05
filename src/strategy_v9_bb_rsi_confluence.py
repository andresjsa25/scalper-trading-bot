"""
Estrategia V9 -- "Rebote de Bollinger en 1h + RSI de 4h" (2026-08-25).

Origen: research_indicator_confluence_scan.py encontró que, de TODOS los
pares posibles entre los 6 indicadores pedidos por el usuario, este es el
único que mostró una ventaja consistente y real en los 10 símbolos:

  - Ancla (1h): el precio hace mecha por fuera de la banda de Bollinger y
    CIERRA de vuelta adentro (indicators/volatility.py: detect_bb_reclaim)
    -- "rebote" de Bollinger.
  - Confirmación (4h): el RSI(14) de 4h está del mismo lado que la
    dirección del rebote (>50 para el rebote alcista, <50 para el bajista)
    -- el ÚLTIMO valor de 4h conocido a esa hora (sin look-ahead).

Números del scan (results/confluence_scan_ranked.csv, results/confluence_scan_all.csv,
horizonte de 1 a 4h, umbral de costos 0.15%): hit-rate agrupado 61-63% en
LOS 10 SÍMBOLOS a la vez (mínimo 55.4%, ninguno por debajo), con
2.500-3.200 señales concluyentes acumuladas según el horizonte -- muestra
grande, no ruido. Comparaciones que se descartaron por no mostrar ventaja:
  - Rebote de Bollinger SOLO (sin RSI): ~51% hit-rate, 0/10 símbolos
    consistentes -- es lo mismo que adivinar.
  - Rebote de Bollinger + RSI leído en la MISMA vela de 1h (no en 4h):
    47-50% hit-rate -- el RSI de la propia temporalidad de entrada no
    aporta nada; es la lectura en la temporalidad MAYOR la que sí funciona.

Esto es un patrón de REVERSIÓN A LA MEDIA de corto plazo, no de tendencia:
apuesta a que, tras una extensión de precio que ya se refleja en la banda
de Bollinger de 1h, el precio vuelve hacia el centro de su rango --
siempre que el RSI de 4h no esté contradiciendo esa vuelta.

Gestión: stop = ATR(14) de 1h x ATR_MULT_STOP, TP = riesgo x rr_ratio
(parámetro, se barre en el backtest). Entrada a MERCADO en el cierre de la
vela de rebote. Validez de la operación acotada a SETUP_VALIDITY_BARS_1H
(~12h) -- coherente con el horizonte de 1-4h donde se midió el patrón, y
con el pedido de "entrar y salir rápido".

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
from backtest import TradeSetup
import config

BB_PERIOD, BB_NUM_STD = 20, 2.0
RSI_PERIOD = 14
ATR_PERIOD = 14
ATR_MULT_STOP = 1.5
SETUP_VALIDITY_BARS_1H = 12  # ~12h, coherente con el horizonte de 1-4h donde se validó el patrón


def prepare(df_4h: pd.DataFrame, df_1h: pd.DataFrame):
    df_4h = df_4h.copy()
    df_4h = add_rsi(df_4h, RSI_PERIOD, "rsi")

    df_1h = df_1h.copy()
    df_1h = add_bollinger_bands(df_1h, BB_PERIOD, BB_NUM_STD)
    df_1h = detect_bb_reclaim(df_1h)
    df_1h = add_atr(df_1h, ATR_PERIOD, "atr")

    df_1h = pd.merge_asof(
        df_1h.sort_values("datetime"),
        df_4h[["datetime", "rsi"]].rename(columns={"rsi": "rsi_4h"}).sort_values("datetime"),
        on="datetime", direction="backward",
    ).reset_index(drop=True)
    return df_4h, df_1h


def generate_setups(symbol: str, df_4h: pd.DataFrame, df_1h: pd.DataFrame, rr_ratio: float = 1.5) -> list:
    _, df = prepare(df_4h, df_1h)

    long_mask = (df["bb_reclaim_bull"] & (df["rsi_4h"] > 50)).fillna(False)
    short_mask = (df["bb_reclaim_bear"] & (df["rsi_4h"] < 50)).fillna(False)

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
            symbol=symbol, strategy="v9_bb_rsi", direction="long",
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
            symbol=symbol, strategy="v9_bb_rsi", direction="short",
            signal_bar_pos=i, signal_datetime=bar["datetime"],
            entry_price_target=entry_price, stop_price=stop_price, take_profit_price=tp_price,
            valid_until_pos=min(i + SETUP_VALIDITY_BARS_1H, n - 1),
            risk_pct=config.RISK_PER_TRADE_PCT, is_limit=False,
        ))

    return setups
