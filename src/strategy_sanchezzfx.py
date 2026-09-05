"""
Estrategia "SANCHEZZFX niveles de sesión" -- video
https://youtu.be/lAN39MqDIQQ ("El Trading es dificil hasta que aplicas
estos 2 conceptos"). Distinta de src/strategy_v2_liquidity_swift.py: esa
usa un swing/fractal estructural como "nivel" (adaptación de una sesión
anterior, documentada como tal en su propio docstring); ESTA usa
literalmente los niveles que pide el video (sesión de Asia/Londres/NY o
máximo-mínimo del día anterior), y respeta la cascada de 3 temporalidades
del video (4h -> 1h -> 5m) tal cual, en vez de comprimirla a 2.

Aislada a propósito de run_live_trading.py / live_trading.py / config.py:
no importa nada de esos módulos salvo TradeSetup y RISK_PER_TRADE_PCT
(dataclass y constante, sin efectos secundarios) -- pensada para
backtesting puro, no toca el bot en vivo.

Traducción del video a reglas medibles (el video no da cifras exactas,
solo la lógica -- ver también session_levels.py):
  1. Nivel: ver indicators/session_levels.py (asia/london/newyork/prevday).
  2. Barrido en 1h: la vela de 1h sobrepasa el nivel con mecha pero CIERRA
     de vuelta (Sweep) -- no un Run (cierre por fuera, se descarta y se
     espera). Dirección: barrido de un máximo -> sesgo VENTA; de un
     mínimo -> sesgo COMPRA.
  3. Alineación con 4h: el video dice "que el barrido en 4 horas y en una
     hora vayan en la misma dirección" / "no pelearte con el marco
     mayor" -- sin cifra exacta de cómo verificarlo. Acá se traduce como
     un VETO: si en las últimas ALIGNMENT_LOOKBACK_4H velas de 4h (mismo
     nivel de sesión, recalculado en 4h) hay un RUN (continuación) en la
     dirección CONTRARIA a la del sweep de 1h, se descarta el setup y se
     espera a que se resuelva -- no se exige que el 4h tenga TAMBIÉN un
     sweep propio (el video no lo pide explícitamente, solo pide que no
     haya fuerza en contra).
  4. Confirmación en 5m: vela ENVOLVENTE (detect_engulfing, ya validada
     contra este mismo video en una sesión anterior) dentro de una
     ventana después del cierre del barrido de 1h. Gatillo de entrada al
     CIERRE de esa vela.
  5. Gestión: stop en la mecha de la vela de 1h que hizo el barrido (no en
     la envolvente). TP = rr_ratio * riesgo (parámetro explícito de esta
     función, NO se lee de config.TP_RR_RATIO -- para no acoplar este
     backtest exploratorio a la config del bot en vivo).

Nota de metodología: igual que strategy_v1_sniper.py / v2_liquidity_swift.py,
la búsqueda de la confirmación en la temporalidad menor arranca en el
timestamp de APERTURA de la vela de 1h que barrió (no en su cierre) --
mismo criterio que las estrategias ya existentes en este proyecto, para
que los resultados sean comparables entre sí. Implica una pequeña
optimista look-ahead ya presente en el resto del proyecto, no introducida
acá.
"""
import os
import sys

import pandas as pd

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "indicators"))
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from indicators.session_levels import compute_session_levels, detect_level_sweep
from indicators.patterns import detect_engulfing
from backtest import TradeSetup
import config

ENGULFING_SEARCH_WINDOW_BARS = 96   # ~8h en 5min para que aparezca la envolvente tras el barrido
SETUP_VALIDITY_BARS = 144           # ~12h en 5min para que la operación se resuelva (SL/TP/time_exit)
STOP_BUFFER_PCT = 0.0005
ALIGNMENT_LOOKBACK_4H = 3           # velas de 4h hacia atrás para chequear que no haya un Run en contra

LEVEL_TYPES = ["asia", "london", "newyork", "prevday"]


def prepare(df_4h: pd.DataFrame, df_1h: pd.DataFrame, df_5m: pd.DataFrame, level_type: str):
    df_1h = compute_session_levels(df_1h.copy(), level_type)
    df_1h = detect_level_sweep(df_1h)
    df_4h = compute_session_levels(df_4h.copy(), level_type)
    df_4h = detect_level_sweep(df_4h)
    df_5m = detect_engulfing(df_5m.copy())
    return df_4h, df_1h, df_5m


def generate_setups(symbol: str, df_4h: pd.DataFrame, df_1h: pd.DataFrame, df_5m: pd.DataFrame,
                     level_type: str = "prevday", rr_ratio: float = 1.0) -> list:
    df_4h, df_1h, df_5m = prepare(df_4h, df_1h, df_5m, level_type)
    setups = []

    entry_datetimes = df_5m["datetime"]
    h4_datetimes = df_4h["datetime"]

    for i in range(len(df_1h)):
        bar = df_1h.iloc[i]
        if bar["sweep_high"]:
            direction = "short"
        elif bar["sweep_low"]:
            direction = "long"
        else:
            continue

        sweep_dt = bar["datetime"]

        # --- alineación con 4h (veto, no exigencia de sweep propio) ---
        h4_pos = int(h4_datetimes.searchsorted(sweep_dt, side="right")) - 1
        if h4_pos < 0:
            continue
        lookback_start = max(0, h4_pos - ALIGNMENT_LOOKBACK_4H + 1)
        window = df_4h.iloc[lookback_start:h4_pos + 1]
        opposing_run_col = "run_high" if direction == "short" else "run_low"
        if window[opposing_run_col].any():
            continue

        # --- confirmación en 5m: envolvente tras el barrido ---
        entry_start_idx = int(entry_datetimes.searchsorted(sweep_dt))
        if entry_start_idx >= len(df_5m):
            continue
        engulf_col = "engulfing_bear" if direction == "short" else "engulfing_bull"
        search_end = min(entry_start_idx + ENGULFING_SEARCH_WINDOW_BARS, len(df_5m) - 1)
        trigger_pos = None
        for k in range(entry_start_idx, search_end + 1):
            if df_5m[engulf_col].iloc[k]:
                trigger_pos = k
                break
        if trigger_pos is None:
            continue

        entry_bar = df_5m.iloc[trigger_pos]
        entry_price = entry_bar["close"]  # entra al cierre de la vela envolvente (mercado)

        # --- gestión: stop en la mecha del barrido de 1h ---
        if direction == "short":
            stop_price = bar["high"] * (1 + STOP_BUFFER_PCT)
            risk = stop_price - entry_price
            if risk <= 0:
                continue
            tp_price = entry_price - risk * rr_ratio
        else:
            stop_price = bar["low"] * (1 - STOP_BUFFER_PCT)
            risk = entry_price - stop_price
            if risk <= 0:
                continue
            tp_price = entry_price + risk * rr_ratio

        setups.append(TradeSetup(
            symbol=symbol, strategy=f"sanchezzfx_{level_type}", direction=direction,
            signal_bar_pos=trigger_pos, signal_datetime=entry_bar["datetime"],
            entry_price_target=entry_price, stop_price=stop_price, take_profit_price=tp_price,
            valid_until_pos=min(trigger_pos + SETUP_VALIDITY_BARS, len(df_5m) - 1),
            risk_pct=config.RISK_PER_TRADE_PCT, is_limit=False,
        ))

    return setups
