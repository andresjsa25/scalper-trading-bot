"""
Motor de simulación de portafolio combinado (extraído de
run_portfolio_simulation.py para poder reusarlo con distintos parámetros,
ej. distinto TP_RR_RATIO, sin duplicar la lógica). Ver ese archivo para
el detalle de las decisiones de diseño (riesgo en dólares fijos, capital
inicial = config.MAX_CAPITAL_USDT, etc.).
"""
import os
from dataclasses import dataclass

import pandas as pd

import config
from strategy_v1_sniper import generate_setups
from entry_filters import apply_entry_filter
from backtest import MAINTENANCE_MARGIN_RATE_ESTIMATE

INITIAL_CAPITAL = config.MAX_CAPITAL_USDT


def load(symbol):
    fname = symbol.replace("/", "_").replace(":", "_")
    df_entry = pd.read_csv(os.path.join(config.DATA_DIR, f"{fname}_15m.csv"))
    df_context = pd.read_csv(os.path.join(config.DATA_DIR, f"{fname}_1h.csv"))
    df_entry["datetime"] = pd.to_datetime(df_entry["datetime"], utc=True)
    df_context["datetime"] = pd.to_datetime(df_context["datetime"], utc=True)
    return df_entry, df_context


def find_exit(df_entry, setup):
    df_slice = df_entry.iloc[setup.signal_bar_pos + 1: setup.valid_until_pos + 1]
    for _, bar in df_slice.iterrows():
        if setup.direction == "long":
            hit_sl = bar["low"] <= setup.stop_price
            hit_tp = bar["high"] >= setup.take_profit_price
        else:
            hit_sl = bar["high"] >= setup.stop_price
            hit_tp = bar["low"] <= setup.take_profit_price
        if hit_sl:
            return setup.stop_price, bar["datetime"], "stop_loss"
        if hit_tp:
            return setup.take_profit_price, bar["datetime"], "take_profit"
    if len(df_slice) == 0:
        return None, None, None
    last_bar = df_slice.iloc[-1]
    return last_bar["close"], last_bar["datetime"], "time_exit"


@dataclass
class OpenPosition:
    symbol: str
    strategy: str
    direction: str
    entry_price: float
    position_size: float
    notional: float
    risk_amount: float
    is_limit: bool
    entry_datetime: pd.Timestamp
    exit_price: float
    exit_datetime: pd.Timestamp
    exit_reason: str


def generate_all_setups(live_config: dict, tp_rr_override: float = None, data_cache: dict = None):
    """Genera y ordena cronológicamente los setups de todos los símbolos de
    live_config. Si tp_rr_override no es None, se usa ESE R:R para TODOS
    los símbolos en vez del tp_rr_ratio individual de cada uno -- para
    poder comparar "qué pasaría si todos usaran 1:2.3" contra la config
    real (cada símbolo con el R:R que se calibró para él)."""
    data_by_symbol = data_cache if data_cache is not None else {}
    all_setups = []

    for symbol, cfg in live_config.items():
        fname = symbol.replace("/", "_").replace(":", "_")
        path = os.path.join(config.DATA_DIR, f"{fname}_15m.csv")
        if not os.path.exists(path):
            continue

        if symbol not in data_by_symbol:
            df_entry, df_context = load(symbol)
            data_by_symbol[symbol] = (df_entry, df_context)
        df_entry, df_context = data_by_symbol[symbol]

        config.TP_RR_RATIO = tp_rr_override if tp_rr_override is not None else cfg["tp_rr_ratio"]
        setups = generate_setups(
            symbol, df_context, df_entry,
            min_swing_percentile=cfg["percentile"], use_trend_filter=cfg["use_trend_filter"],
            use_session_filter=cfg["use_session_filter"], require_regime=cfg["require_regime"],
        )
        setups = apply_entry_filter(setups, df_entry, cfg["ema_filter"])
        all_setups.extend(setups)

    all_setups.sort(key=lambda s: s.signal_datetime)
    return all_setups, {s: dfs[0] for s, dfs in data_by_symbol.items()}


def run_simulation(live_config: dict, tp_rr_override: float = None, data_cache: dict = None):
    """Corre la simulación de portafolio combinado y devuelve
    (trades_df, equity_df) -- equity_df tiene columnas datetime/capital,
    un punto por cada cierre de operación (más el punto inicial)."""
    all_setups, data_by_symbol = generate_all_setups(live_config, tp_rr_override, data_cache)
    if not all_setups:
        return pd.DataFrame(), pd.DataFrame(columns=["datetime", "capital"])

    start_dt = all_setups[0].signal_datetime
    capital = INITIAL_CAPITAL
    open_risk = 0.0
    open_by_symbol = set()
    pending_closes = []
    closed_trades = []
    equity_points = [(start_dt, capital)]

    def close_due(up_to_datetime):
        nonlocal capital, open_risk
        pending_closes.sort(key=lambda x: x[0])
        while pending_closes and pending_closes[0][0] <= up_to_datetime:
            _, pos = pending_closes.pop(0)
            open_by_symbol.discard(pos.symbol)

            entry_fee_rate = config.MAKER_FEE_PCT if pos.is_limit else config.TAKER_FEE_PCT
            exit_fee_rate = config.TAKER_FEE_PCT
            entry_slip = pos.entry_price * config.SLIPPAGE_PCT_ESTIMATE
            exit_slip = pos.exit_price * config.SLIPPAGE_PCT_ESTIMATE
            if pos.direction == "long":
                eff_entry = pos.entry_price + entry_slip
                eff_exit = pos.exit_price - exit_slip
                pnl_gross = (eff_exit - eff_entry) * pos.position_size
            else:
                eff_entry = pos.entry_price - entry_slip
                eff_exit = pos.exit_price + exit_slip
                pnl_gross = (eff_entry - eff_exit) * pos.position_size

            entry_fee = pos.notional * entry_fee_rate
            exit_fee = (pos.position_size * pos.exit_price) * exit_fee_rate
            pnl_net = pnl_gross - entry_fee - exit_fee

            capital += pnl_net
            open_risk -= pos.risk_amount
            closed_trades.append({
                "symbol": pos.symbol, "strategy": pos.strategy, "direction": pos.direction,
                "entry_datetime": pos.entry_datetime, "exit_datetime": pos.exit_datetime,
                "exit_reason": pos.exit_reason, "pnl_net": pnl_net,
                "r_multiple": pnl_net / pos.risk_amount if pos.risk_amount else 0,
                "capital_after": capital,
            })
            equity_points.append((pos.exit_datetime, capital))

    for setup in all_setups:
        if capital <= 0:
            break
        close_due(setup.signal_datetime)

        if setup.symbol in open_by_symbol:
            continue
        if len(pending_closes) >= config.MAX_CONCURRENT_TRADES:
            continue

        entry_price = setup.entry_price_target
        stop_price = setup.stop_price
        stop_distance_pct = abs(entry_price - stop_price) / entry_price
        liq_buffer = (1 / config.LEVERAGE) - MAINTENANCE_MARGIN_RATE_ESTIMATE
        if stop_distance_pct >= liq_buffer:
            continue

        risk_amount = config.MAX_CAPITAL_USDT * setup.risk_pct
        if (open_risk + risk_amount) / config.MAX_CAPITAL_USDT > config.MAX_PORTFOLIO_RISK_PCT:
            continue

        position_size = risk_amount / abs(entry_price - stop_price)
        notional = position_size * entry_price
        margin_required = notional / config.LEVERAGE
        if margin_required > capital:
            position_size = (capital * config.LEVERAGE) / entry_price
            notional = position_size * entry_price

        df_entry = data_by_symbol[setup.symbol]
        exit_price, exit_dt, exit_reason = find_exit(df_entry, setup)
        if exit_price is None:
            continue

        pos = OpenPosition(
            symbol=setup.symbol, strategy=setup.strategy, direction=setup.direction,
            entry_price=entry_price, position_size=position_size, notional=notional,
            risk_amount=risk_amount, is_limit=setup.is_limit, entry_datetime=setup.signal_datetime,
            exit_price=exit_price, exit_datetime=exit_dt, exit_reason=exit_reason,
        )
        open_by_symbol.add(setup.symbol)
        open_risk += risk_amount
        pending_closes.append((exit_dt, pos))

    close_due(pd.Timestamp.max.tz_localize("UTC"))

    trades_df = pd.DataFrame(closed_trades)
    equity_df = pd.DataFrame(equity_points, columns=["datetime", "capital"]).sort_values("datetime").reset_index(drop=True)
    return trades_df, equity_df
