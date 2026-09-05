"""
Ciclo de trading EN VIVO con dinero real en BingX.

  - V1 (Sniper de liquidez, 15min/1h, 15x): SILVER, SP500, NASDAQ100,
    OIL_BRENT, XAUT, AMZN, ADA, BNB (calibración original, 2026-08-04) +
    AAPL, ETH, HYPE, SOL, BTC (migrados desde V5 el 2026-08-08: al
    backtestear V5 en estos 5 activos contra V1 con la misma config, V1
    ganaba en 4/5 -- AAPL/ETH/HYPE/SOL con los defaults del módulo
    (percentil 0, sin filtro de tendencia, EMA10 solo), BTC con un grid
    search corto propio -- percentil 40 + EMA10+T-Theory, el resto de la
    grilla no mejoraba sobre el baseline o tenía muestra insuficiente
    para confiar). Ver results/live_config_performance.csv,
    results/v5_symbols_on_v1_summary.csv y
    results/v1_btc_eth_calibration_all.csv para el detalle completo.
    AMZN sacado de V1 el 2026-09-05 (3-4 pérdidas seguidas en vivo) -- ver
    el comentario en V1_LIVE_CONFIG más abajo. Reemplazo previsto: EUR/USD
    y USD/JPY, sujeto a backtesting (fetch_data_forex.py).
    NASDAQ100 sacado y GOOGL/META/NVDA sumados el 2026-09-05, en base al
    backtest de 3 estrategias + walk-forward sobre estos 4 activos (ver
    results/backtest_3strategies_comparison.csv y
    results/stocks_test_walkforward_summary_combined.csv) -- RUSSELL2000
    quedó afuera de plano, BingX tiene pausado su histórico (símbolo
    NCSIRUSSELL20002USD, error 109415).
  - V5 (Retroceso de Fibonacci, 1h/4h, 50x, R:R>=1.5): GOOGL sumado el
    2026-09-05 -- único activo de los 4 evaluados donde V5 también dio
    resultado propio (PF>1) en la comparación de 3 estrategias, además de
    V1. El resto de los activos de V1 no pasaron por V5 (no se evaluó, no
    que haya dado mal).
  - V10 (Rebote de Bollinger 1h + RSI 4h, 15x): agregada 2026-08-08+18 días
    después (2026-08-25) como SEGUNDA estrategia -- NO reemplaza a V1 -- para
    BTC, ETH, HYPE, SOL, ADA, BNB (los 6 cripto nativos que ya opera V1).
    Objetivo explícito: sumar más frecuencia de señales, no superar a V1 --
    en la comparación más limpia disponible (misma ventana de ~100 días,
    ver results/v1_vs_v10_matched_window.csv), V1 sigue con mejor profit
    factor en los 6 activos, pero V10 se mantiene rentable (PF>1) y opera
    bastante más seguido. Si V1 ya tiene una posición abierta en un símbolo,
    V10 no abre una segunda ahí (y viceversa) -- ver V10_LIVE_CONFIG.

Capital compartido entre las 3 estrategias, topeado en config.MAX_CAPITAL_USDT,
mismos topes de riesgo de portafolio (30% / 10 operaciones simultáneas).

Para detener el bot en cualquier momento: crear un archivo vacío llamado
STOP_TRADING.flag en la raíz del proyecto.
"""
import os
import sys

import pandas as pd

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
import config
from strategy_v1_sniper import generate_setups as generate_setups_v1
from strategy_v5_fib_pullback import generate_setups as generate_setups_v5
from strategy_v10_bb_rsi_refined import generate_setups as generate_setups_v10
from live_data import update_live_data
from entry_filters import apply_entry_filter
import live_trading as lt

V1_LEVERAGE = 15
V5_LEVERAGE = 50
V10_LEVERAGE = 15  # mismo config.LEVERAGE que se usó en todo el backtesting de V10

V1_LIVE_CONFIG = {
    "NCCOXAG2USD/USDT:USDT": {"percentile": 0, "use_trend_filter": False, "use_session_filter": True,
                               "require_regime": None, "tp_rr_ratio": 2.3, "ema_filter": "ema_t"},
    "NCSISP5002USD/USDT:USDT": {"percentile": 20, "use_trend_filter": False, "use_session_filter": True,
                                 "require_regime": None, "tp_rr_ratio": 2.3, "ema_filter": "ema_only"},
    # "NCSINASDAQ1002USD/USDT:USDT" -- sacado (sep 2026): backtest de V1 dio
    # PF 0.98 en 100 días reales, y el walk-forward out-of-sample confirmó
    # PF 0.71 / retorno -7.65% -- no se sostiene, mismo criterio que AMZN.
    # Ver results/backtest_3strategies_comparison.csv y
    # results/stocks_test_walkforward_summary_combined.csv.
    "NCCO1OILBRENT2USD/USDT:USDT": {"percentile": 0, "use_trend_filter": False, "use_session_filter": True,
                                     "require_regime": None, "tp_rr_ratio": 2.3, "ema_filter": "ema_t"},
    "XAUT/USDT:USDT": {"percentile": 0, "use_trend_filter": True, "use_session_filter": False,
                        "require_regime": None, "tp_rr_ratio": 2.3, "ema_filter": "ema_only"},
    # "NCSKAMZN2USD/USDT:USDT" -- sacado (sep 2026): 3-4 pérdidas seguidas en
    # vivo. La posición que ya estaba abierta al momento de sacarlo del
    # config sigue su curso normal -- su SL/TP quedaron puestos directo en
    # BingX (adjuntos a la orden de entrada), así que se cierran solos pase
    # lo que pase con este archivo; ver state.json / logs para el resultado
    # final de esa operación. Reemplazo previsto: EUR/USD y USD/JPY, una vez
    # que el backtesting con datos de Dukascopy diga con qué estrategia/
    # config conviene sumarlos (ver fetch_data_forex.py).
    "ADA/USDT:USDT": {"percentile": 0, "use_trend_filter": False, "use_session_filter": True,
                       "require_regime": None, "tp_rr_ratio": 2.3, "ema_filter": "ema_t"},
    "BNB/USDT:USDT": {"percentile": 0, "use_trend_filter": False, "use_session_filter": True,
                       "require_regime": None, "tp_rr_ratio": 2.3, "ema_filter": "ema_only"},
    # --- Migrados desde V5 el 2026-08-08 (ver docstring del módulo) ---
    "NCSKAAPL2USD/USDT:USDT": {"percentile": 0, "use_trend_filter": False, "use_session_filter": True,
                                "require_regime": None, "tp_rr_ratio": 2.3, "ema_filter": "ema_only"},
    "ETH/USDT:USDT": {"percentile": 0, "use_trend_filter": False, "use_session_filter": True,
                       "require_regime": None, "tp_rr_ratio": 2.3, "ema_filter": "ema_only"},
    "HYPE/USDT:USDT": {"percentile": 0, "use_trend_filter": False, "use_session_filter": True,
                        "require_regime": None, "tp_rr_ratio": 2.3, "ema_filter": "ema_only"},
    "SOL/USDT:USDT": {"percentile": 0, "use_trend_filter": False, "use_session_filter": True,
                       "require_regime": None, "tp_rr_ratio": 2.3, "ema_filter": "ema_only"},
    "BTC/USDT:USDT": {"percentile": 40, "use_trend_filter": False, "use_session_filter": True,
                       "require_regime": None, "tp_rr_ratio": 2.3, "ema_filter": "ema_t"},
    # --- Sumados sep 2026: backtest de V1 (config idéntica a AAPL) + walk-forward
    # out-of-sample dieron PF>=1.7 y retorno positivo sostenido para los 3. Ver
    # results/backtest_3strategies_comparison.csv y
    # results/stocks_test_walkforward_summary_combined.csv. ---
    "NCSKGOOGL2USD/USDT:USDT": {"percentile": 0, "use_trend_filter": False, "use_session_filter": True,
                                 "require_regime": None, "tp_rr_ratio": 2.3, "ema_filter": "ema_only"},
    "NCSKMETA2USD/USDT:USDT": {"percentile": 0, "use_trend_filter": False, "use_session_filter": True,
                                "require_regime": None, "tp_rr_ratio": 2.3, "ema_filter": "ema_only"},
    "NCSKNVDA2USD/USDT:USDT": {"percentile": 0, "use_trend_filter": False, "use_session_filter": True,
                                "require_regime": None, "tp_rr_ratio": 2.3, "ema_filter": "ema_only"},
}
# GOOGL sumado sep 2026 -- único activo donde V5 (Fibonacci) también dio
# resultado propio en la comparación de 3 estrategias (PF 1.18 en 240 días,
# de fábrica sin calibrar) además de V1 -- el usuario pidió correr ambas acá.
# Config "de fábrica" del módulo (sin filtro de percentil, sin R:R mínimo
# exigido): no hay una versión ya calibrada de V5 para acciones, a
# diferencia de V1. Si el resultado en vivo no convence, calibrar por
# separado antes de asumir que esto es definitivo.
V5_LIVE_CONFIG = {
    "NCSKGOOGL2USD/USDT:USDT": {"percentile": 0, "min_rr_ratio": 0},
}

# --- V10 (Rebote de Bollinger 1h + RSI 4h) -- agregada 2026-08-25 como SEGUNDA
# estrategia, en paralelo a V1, solo para los 6 cripto nativos que ya opera V1
# (no reemplaza nada, no se toca V1_LIVE_CONFIG). Objetivo: sumar más
# frecuencia de operaciones, no reemplazar a V1 -- en el backtest sobre la
# ventana más reciente y comparable (~100 días, ver results/v1_vs_v10_matched_window.csv
# y results/v10_rr_sweep_window.csv) V1 sigue ganando en profit factor en los
# 6 activos, pero V10 aporta bastantes más señales y se mantiene rentable
# (PF>1) con estos parámetros. rr_ratio quedó en 1:2 salvo ETH y BNB, donde
# 1:2.5 mejoró de forma consistente tanto en el histórico completo como en
# la ventana reciente (ver results/v10_rr_sweep_full.csv).
#
# IMPORTANTE: si V1 ya tiene una posición abierta en un símbolo, V10 NO va a
# abrir una segunda posición ahí (y viceversa) -- lo bloquea el chequeo
# existente de `open_symbols` en process_new_setups, que es por símbolo, no
# por estrategia. No se cambió esa lógica a propósito: evita duplicar
# exposición sobre el mismo activo.
V10_LIVE_CONFIG = {
    "BTC/USDT:USDT":  {"stop_mode": "atr",  "atr_mult": 1.8,               "require_pattern": False, "rr_ratio": 2.0},
    "ETH/USDT:USDT":  {"stop_mode": "atr",  "atr_mult": 1.2,               "require_pattern": False, "rr_ratio": 2.5},
    "HYPE/USDT:USDT": {"stop_mode": "wick", "wick_buffer_atr_frac": 0.1,   "require_pattern": False, "rr_ratio": 2.0},
    "SOL/USDT:USDT":  {"stop_mode": "atr",  "atr_mult": 1.2,               "require_pattern": False, "rr_ratio": 2.0},
    "ADA/USDT:USDT":  {"stop_mode": "atr",  "atr_mult": 1.2,               "require_pattern": False, "rr_ratio": 2.0},
    "BNB/USDT:USDT":  {"stop_mode": "wick", "wick_buffer_atr_frac": 0.2,   "require_pattern": True,  "rr_ratio": 2.5},
}

ALL_SYMBOLS = sorted(set(list(V1_LIVE_CONFIG.keys()) + list(V5_LIVE_CONFIG.keys()) + list(V10_LIVE_CONFIG.keys())))
LEVERAGE_BY_SYMBOL = {s: V1_LEVERAGE for s in V1_LIVE_CONFIG}
LEVERAGE_BY_SYMBOL.update({s: V5_LEVERAGE for s in V5_LIVE_CONFIG})
LEVERAGE_BY_SYMBOL.update({s: V10_LEVERAGE for s in V10_LIVE_CONFIG})


def process_new_setups(exchange, symbol_setups, state, risk_base_capital, available_capital,
                        current_open_risk, current_open_count, leverage, open_symbols):
    for setup in symbol_setups:
        if lt.kill_switch_active():
            lt.log("STOP_TRADING.flag detectado a mitad de ciclo -- deteniendo antes de abrir más.")
            break
        if setup.symbol in open_symbols:
            lt.log(f"  [salteada] {setup.symbol} {setup.strategy}: ya hay una posición/orden abierta "
                   f"en este símbolo -- no se apilan operaciones (mismo criterio que el backtest).")
            continue
        if current_open_count >= config.MAX_CONCURRENT_TRADES:
            lt.log(f"  [salteada] {setup.symbol} {setup.strategy}: tope de "
                   f"{config.MAX_CONCURRENT_TRADES} operaciones simultáneas alcanzado.")
            continue

        sized = lt.compute_valid_position_size(
            exchange, setup.symbol, risk_base_capital, setup.risk_pct,
            setup.entry_price_target, setup.stop_price, leverage,
            available_capital=available_capital,
        )
        if sized is None:
            continue
        position_size, risk_amount = sized

        if (current_open_risk + risk_amount) / risk_base_capital > config.MAX_PORTFOLIO_RISK_PCT:
            lt.log(f"  [salteada] {setup.symbol} {setup.strategy}: superaría el "
                   f"{config.MAX_PORTFOLIO_RISK_PCT*100:.0f}% de riesgo abierto de portafolio.")
            continue

        try:
            order = lt.place_entry_with_sl_tp(exchange, setup, position_size)
            if order is None:
                # Señal descartada dentro de place_entry_with_sl_tp (ej. SL ya
                # invalidado por el precio actual) -- ya se logueo el motivo ahi,
                # no hay orden que registrar.
                continue
            state["open_orders"].append({
                "symbol": setup.symbol, "strategy": setup.strategy, "order_id": order.get("id"),
                "risk_amount": risk_amount, "signal_datetime": str(setup.signal_datetime),
            })
            current_open_risk += risk_amount
            current_open_count += 1
            open_symbols.add(setup.symbol)
        except Exception as e:
            lt.log(f"  [ERROR al colocar orden] {setup.symbol} {setup.strategy}: {e}")

    return current_open_risk, current_open_count


def main():
    if lt.kill_switch_active():
        lt.log("STOP_TRADING.flag detectado -- no se abren posiciones nuevas. "
               "Borrá ese archivo para reanudar.")
        return

    exchange = lt.get_exchange()
    lt.ensure_leverage(exchange, ALL_SYMBOLS, leverage=LEVERAGE_BY_SYMBOL)

    balance = exchange.fetch_balance()
    free_balance = balance.get("USDT", {}).get("free", 0) or 0
    # El riesgo (2%) se calcula siempre sobre el balance REAL de la cuenta,
    # sin piso ni techo -- si sube a $400 arriesga sobre $400, si baja a
    # $200 arriesga sobre $200. Cambiado a pedido del usuario 2026-08-25
    # (antes tenía un piso fijo en config.MAX_CAPITAL_USDT; ver historial
    # si hace falta volver a esa versión). config.MAX_CAPITAL_USDT queda
    # sin usar acá -- se deja definida en config.py solo como referencia,
    # no participa más en el sizing.
    risk_base_capital = free_balance
    lt.log(f"Capital libre en cuenta: ${free_balance:.2f} | Base de riesgo (balance real, sin piso): ${risk_base_capital:.2f}")
    if free_balance <= 0:
        lt.log("Sin capital disponible. Abortando ciclo.")
        return

    state = lt._load_state()
    own_open_orders = lt.fetch_own_open_orders(exchange)
    open_position_symbols = lt.fetch_open_position_symbols(exchange, ALL_SYMBOLS)
    lt.log(f"Órdenes propias abiertas (V1+V5): {len(own_open_orders)} | "
           f"Símbolos con posición ya abierta: {len(open_position_symbols)}")

    # Símbolos que YA tienen una orden pendiente O una posición abierta en el
    # exchange -- se usa para no apilar una entrada nueva sobre una operación
    # ya establecida (con su SL/TP puestos), igual que asume el backtest
    # ("una operación abierta a la vez, no se apilan" -- backtest.py línea 59).
    # Se combinan ambas fuentes porque fetch_open_orders() deja de ver la
    # entrada en cuanto se llena, aunque la posición siga abierta.
    open_symbols = {o["symbol"] for o in own_open_orders} | open_position_symbols

    # Reconciliación de state["open_orders"] contra el exchange. Antes esta
    # lista SOLO se agregaba (process_new_setups la appendea, nada la
    # limpiaba): cuando una posición cerraba por SL/TP quedaba una entrada
    # fantasma para siempre. Con 10 fantasmas acumulados y
    # MAX_CONCURRENT_TRADES=10, la primera compuerta de process_new_setups
    # rechazaba TODA señal nueva -> el bot dejó de operar ~1 semana sin
    # error visible. Cada ciclo: si el símbolo de una entrada registrada ya
    # no tiene ni orden pendiente ni posición abierta en el exchange, es una
    # operación cerrada -> se descarta del estado.
    stale = [o for o in state["open_orders"] if o["symbol"] not in open_symbols]
    if stale:
        lt.log(f"  [reconciliación] {len(stale)} orden(es) registradas ya cerradas en el "
               f"exchange -- se limpian del estado: "
               f"{', '.join(sorted({o['symbol'] for o in stale}))}")
        state["open_orders"] = [o for o in state["open_orders"] if o["symbol"] in open_symbols]

    current_open_risk = sum(o.get("risk_amount", 0) for o in state["open_orders"])
    current_open_count = len(state["open_orders"])

    if len(own_open_orders) > current_open_count:
        lt.log(f"[!] AVISO: el exchange muestra más órdenes propias abiertas ({len(own_open_orders)}) "
               f"que nuestro registro local ({current_open_count}). No se abren posiciones nuevas "
               f"este ciclo por seguridad.")
        return

    # --- V1 ---
    for symbol, cfg in V1_LIVE_CONFIG.items():
        try:
            lt.log(f"--- [V1] {symbol} ---")
            config.TP_RR_RATIO = cfg["tp_rr_ratio"]
            df_entry = update_live_data(exchange, symbol, "15m")
            df_context = update_live_data(exchange, symbol, "1h")

            symbol_setups = generate_setups_v1(
                symbol, df_context, df_entry,
                min_swing_percentile=cfg["percentile"], use_trend_filter=cfg["use_trend_filter"],
                use_session_filter=cfg["use_session_filter"], require_regime=cfg["require_regime"],
            )
            symbol_setups = apply_entry_filter(symbol_setups, df_entry, cfg["ema_filter"])
            last_processed = state["last_processed_signal"].get(symbol)
            last_processed_ts = pd.Timestamp(last_processed) if last_processed else pd.Timestamp.now(tz="UTC")
            genuinely_new = sorted(
                [s for s in symbol_setups if s.signal_datetime > last_processed_ts],
                key=lambda s: s.signal_datetime,
            )
            current_open_risk, current_open_count = process_new_setups(
                exchange, genuinely_new, state, risk_base_capital, free_balance,
                current_open_risk, current_open_count, V1_LEVERAGE, open_symbols)
            if symbol_setups:
                # Avanzar la marca al setup MÁS RECIENTE que se vio, no a la
                # última vela. Un setup puede confirmarse tarde (los fractales
                # necesitan 2 velas a cada lado + zigzag + CHoCH): aparece un
                # ciclo después con un timestamp anterior a la última vela. Con
                # el criterio viejo (str(df_entry["datetime"].iloc[-1])) la
                # marca ya había saltado a esa última vela y ese setup quedaba
                # descartado como "no nuevo" para siempre. max() con
                # last_processed_ts garantiza que la marca nunca retroceda.
                newest_setup_ts = max(s.signal_datetime for s in symbol_setups)
                state["last_processed_signal"][symbol] = str(max(last_processed_ts, newest_setup_ts))
        except Exception as e:
            # Un símbolo roto (dato corrupto, error puntual de API, etc.) no
            # debe tumbar el resto del ciclo -- eso fue justo lo que pasó el
            # 2026-08-26 con el CSV vacío de ETH: un solo símbolo hizo
            # crashear TODO el script antes de llegar a lt._save_state(),
            # perdiendo el progreso ya hecho de los símbolos anteriores (y
            # dejando el estado desactualizado durante dos semanas sin que
            # nadie lo notara).
            lt.log(f"  [ERROR en símbolo, se saltea este ciclo] [V1] {symbol}: {e}")

    # --- V5 ---
    for symbol, cfg in V5_LIVE_CONFIG.items():
        try:
            lt.log(f"--- [V5] {symbol} ---")
            df_entry = update_live_data(exchange, symbol, "1h")
            df_context = update_live_data(exchange, symbol, "4h")

            symbol_setups = generate_setups_v5(
                symbol, df_context, df_entry,
                min_swing_percentile=cfg["percentile"], min_rr_ratio=cfg["min_rr_ratio"],
            )
            last_processed = state["last_processed_signal"].get(symbol)
            last_processed_ts = pd.Timestamp(last_processed) if last_processed else pd.Timestamp.now(tz="UTC")
            genuinely_new = sorted(
                [s for s in symbol_setups if s.signal_datetime > last_processed_ts],
                key=lambda s: s.signal_datetime,
            )
            current_open_risk, current_open_count = process_new_setups(
                exchange, genuinely_new, state, risk_base_capital, free_balance,
                current_open_risk, current_open_count, V5_LEVERAGE, open_symbols)
            if symbol_setups:
                # Marca al setup más reciente visto, sin retroceder -- ver V1.
                newest_setup_ts = max(s.signal_datetime for s in symbol_setups)
                state["last_processed_signal"][symbol] = str(max(last_processed_ts, newest_setup_ts))
        except Exception as e:
            lt.log(f"  [ERROR en símbolo, se saltea este ciclo] [V5] {symbol}: {e}")

    # --- V10 (segunda estrategia en paralelo a V1, ver V10_LIVE_CONFIG arriba) ---
    for symbol, cfg in V10_LIVE_CONFIG.items():
        try:
            lt.log(f"--- [V10] {symbol} ---")
            df_entry = update_live_data(exchange, symbol, "1h")
            df_context = update_live_data(exchange, symbol, "4h")

            symbol_setups = generate_setups_v10(symbol, df_context, df_entry, **cfg)
            # Clave de estado con prefijo "v10:" -- V1 ya usa el símbolo pelado
            # como clave de last_processed_signal; si V10 usara la misma clave
            # para un símbolo que V1 también opera (son los mismos 6), una
            # estrategia pisaría el timestamp de la otra y se rompería la
            # deduplicación de señales de ambas.
            state_key = f"v10:{symbol}"
            last_processed = state["last_processed_signal"].get(state_key)
            last_processed_ts = pd.Timestamp(last_processed) if last_processed else pd.Timestamp.now(tz="UTC")
            genuinely_new = sorted(
                [s for s in symbol_setups if s.signal_datetime > last_processed_ts],
                key=lambda s: s.signal_datetime,
            )
            current_open_risk, current_open_count = process_new_setups(
                exchange, genuinely_new, state, risk_base_capital, free_balance,
                current_open_risk, current_open_count, V10_LEVERAGE, open_symbols)
            if symbol_setups:
                # Marca al setup más reciente visto, sin retroceder -- ver V1.
                newest_setup_ts = max(s.signal_datetime for s in symbol_setups)
                state["last_processed_signal"][state_key] = str(max(last_processed_ts, newest_setup_ts))
        except Exception as e:
            lt.log(f"  [ERROR en símbolo, se saltea este ciclo] [V10] {symbol}: {e}")

    lt._save_state(state)
    lt.log("Ciclo de trading en vivo completado.\n")


if __name__ == "__main__":
    main()
