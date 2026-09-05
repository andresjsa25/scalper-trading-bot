"""
Estrategia V6 -- "Order flow proxy", v2 calibración (ver historial de
cambios abajo). Inspirada SOLO en los fragmentos cuantificables del video
"Trading LIVE with the #1 Scalper in the WORLD" / Fabio Valentini, canal
Chart Fanatics -- NO es la estrategia real del video (que es discrecional
por diseño, el propio trader dice que la entrada "no se puede automatizar").

Reglas que quedan del video:
  - Confirmación por cierre de vela completo más allá de un swing, no una
    mecha ("I want a full candle close").
  - Proxy de "agresión"/"órdenes grandes": volumen relativo >= VOLUME_THRESHOLD
    veces el promedio de las últimas VOLUME_LOOKBACK velas (no es order flow
    real, que no existe en el histórico de velas de BingX).

Cambios pedidos por el usuario en esta calibración (2026-08-05):
  - Timeframe 15m -> 5m (más señales por día).
  - Se saca el requisito del "segundo impulso completo" (que necesitaba un
    retroceso y una segunda ruptura -- muy poco frecuente). El stop pasa a
    ser el extremo (low/high) de la vela de ruptura, no el retroceso entre
    dos impulsos.
  - Gestión de riesgo: se saca el 0.3%/R:R 1:3 propios del video, se usa
    la MISMA gestión que el resto del bot (config.RISK_PER_TRADE_PCT,
    config.TP_RR_RATIO) para que sea comparable con V1/V5.
  - Sesión: Nueva York Y Londres (antes solo NY) -- vuelve a usar
    session_filter.in_session(), que ya valida ambas ventanas.
  - Primera vuelta (solo ruptura + volumen, sin ningún filtro de
    sostenimiento) dio win rate 28-40% y con 2% de riesgo por operación
    reventó la cuenta en 5 de 6 activos (retornos de -76% a -91% en 74-85
    días). Se restaura un filtro de confirmación MÁS LIVIANO que el
    segundo impulso completo: en vez de exigir retroceso + nueva ruptura,
    exige que las próximas CONFIRMATION_BARS velas sostengan el cierre más
    allá del nivel (sin volver a cerrar del otro lado) antes de entrar --
    ataca la misma idea del video (evitar fakeouts) sin frenar tanto la
    frecuencia como el segundo impulso completo.

Sigue sin implementar (limitación conocida, el motor de backtest
compartido no lo soporta): stop dinámico a breakeven, límite de pérdida
diaria.
"""
import os
import sys

import pandas as pd

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "indicators"))
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from indicators.liquidity import find_raw_fractals, build_zigzag_swings
from indicators.volume import add_relative_volume
from session_filter import in_session
from backtest import TradeSetup

VOLUME_LOOKBACK = 20
VOLUME_THRESHOLD = 1.5      # vela de ruptura necesita >= 1.5x el volumen promedio
DRIVE_MAX_BARS = 20         # velas máximas de espera para la ruptura tras el swing
CONFIRMATION_BARS = 2       # velas que deben sostener la ruptura antes de entrar
SETUP_VALIDITY_BARS = 96    # ~8h en 5min para que la operación se resuelva
STOP_BUFFER_PCT = 0.001


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    df = find_raw_fractals(df.copy(), n=2)
    df = add_relative_volume(df, period=VOLUME_LOOKBACK)
    return df


def generate_setups(symbol: str, df: pd.DataFrame) -> list:
    df = prepare(df)
    swings = build_zigzag_swings(df).sort_values("pos").reset_index(drop=True)
    setups = []

    for i in range(len(swings)):
        swing = swings.iloc[i]
        swing_pos = int(swing["pos"])
        swing_price = swing["price"]
        direction = "long" if swing["type"] == "high" else "short"

        # --- Ruptura: cierre completo más allá del swing, con volumen alto, en sesión ---
        drive_pos = None
        search_end = min(swing_pos + DRIVE_MAX_BARS, len(df) - 1)
        for j in range(swing_pos + 1, search_end + 1):
            bar = df.iloc[j]
            closed_beyond = bar["close"] > swing_price if direction == "long" else bar["close"] < swing_price
            if not closed_beyond:
                continue
            if pd.isna(bar["rel_volume"]) or bar["rel_volume"] < VOLUME_THRESHOLD:
                continue
            if not in_session(bar["datetime"]):
                continue
            drive_pos = j
            break
        if drive_pos is None:
            continue

        # --- Confirmación: las próximas CONFIRMATION_BARS velas sostienen la ruptura ---
        confirm_end = min(drive_pos + CONFIRMATION_BARS, len(df) - 1)
        if confirm_end < drive_pos + CONFIRMATION_BARS:
            continue  # no hay suficientes velas para confirmar antes del final de los datos

        held = True
        for k in range(drive_pos + 1, confirm_end + 1):
            bar_k = df.iloc[k]
            failed = bar_k["close"] < swing_price if direction == "long" else bar_k["close"] > swing_price
            if failed:
                held = False
                break
        if not held:
            continue

        entry_pos = confirm_end
        entry_price = df["close"].iloc[entry_pos]

        window = df.iloc[drive_pos:entry_pos + 1]
        if direction == "long":
            stop_price = window["low"].min() * (1 - STOP_BUFFER_PCT)
        else:
            stop_price = window["high"].max() * (1 + STOP_BUFFER_PCT)

        risk = entry_price - stop_price if direction == "long" else stop_price - entry_price
        if risk <= 0:
            continue
        tp_price = entry_price + risk * config.TP_RR_RATIO if direction == "long" \
            else entry_price - risk * config.TP_RR_RATIO

        setups.append(TradeSetup(
            symbol=symbol, strategy="v6_orderflow_proxy", direction=direction,
            signal_bar_pos=entry_pos, signal_datetime=df.iloc[entry_pos]["datetime"],
            entry_price_target=entry_price, stop_price=stop_price, take_profit_price=tp_price,
            valid_until_pos=min(entry_pos + SETUP_VALIDITY_BARS, len(df) - 1),
            risk_pct=config.RISK_PER_TRADE_PCT, is_limit=False,
        ))

    return setups
