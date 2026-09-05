"""
Motor de backtest: mismo modelo de costos y gestión de riesgo que
fibo-reversal-bot/src/backtest.py (comisiones reales de BingX, slippage
estimado, chequeo de liquidación) -- reimplementado acá porque este es un
proyecto separado, pero sin cambiar ninguna cifra.
"""
import os
import sys
from dataclasses import dataclass

import numpy as np
import pandas as pd

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

MAINTENANCE_MARGIN_RATE_ESTIMATE = 0.004  # ver fibo-reversal-bot/src/backtest.py -- misma estimación


@dataclass
class TradeSetup:
    symbol: str
    strategy: str            # 'v1_sniper', 'v2_liquidity_swift', 'v3_crt', 'v4_hybrid'
    direction: str            # 'long' / 'short'
    signal_bar_pos: int
    signal_datetime: pd.Timestamp
    entry_price_target: float
    stop_price: float
    take_profit_price: float
    valid_until_pos: int
    risk_pct: float = config.RISK_PER_TRADE_PCT
    is_limit: bool = False   # True = orden límite (fee maker), False = mercado (fee taker)


@dataclass
class TradeResult:
    symbol: str
    strategy: str
    direction: str
    entry_datetime: pd.Timestamp
    entry_price: float
    exit_datetime: pd.Timestamp
    exit_price: float
    exit_reason: str
    stop_price: float
    take_profit_price: float
    position_size: float
    notional: float
    fees_paid: float
    pnl_gross: float
    pnl_net: float
    capital_before: float
    capital_after: float
    r_multiple: float


def simulate_trades(setups: list, df_entry: pd.DataFrame, initial_capital: float) -> list:
    """Simula en orden cronológico. Una operación abierta a la vez (no se apilan)."""
    results = []
    capital = initial_capital

    setups_sorted = sorted(setups, key=lambda s: s.signal_bar_pos)
    last_exit_pos = -1

    for setup in setups_sorted:
        if setup.signal_bar_pos <= last_exit_pos:
            continue

        entry_price = setup.entry_price_target
        stop_price = setup.stop_price
        tp_price = setup.take_profit_price

        stop_distance_pct = abs(entry_price - stop_price) / entry_price
        liq_buffer = (1 / config.LEVERAGE) - MAINTENANCE_MARGIN_RATE_ESTIMATE
        if stop_distance_pct >= liq_buffer:
            continue

        risk_amount = capital * setup.risk_pct
        position_size = risk_amount / abs(entry_price - stop_price)
        notional = position_size * entry_price
        margin_required = notional / config.LEVERAGE
        if margin_required > capital:
            position_size = (capital * config.LEVERAGE) / entry_price
            notional = position_size * entry_price

        df_slice = df_entry.iloc[setup.signal_bar_pos + 1: setup.valid_until_pos + 1]

        exit_price = None
        exit_dt = None
        exit_reason = "no_exit_data"
        exit_pos = setup.valid_until_pos

        for offset, (_, bar) in enumerate(df_slice.iterrows()):
            pos = setup.signal_bar_pos + 1 + offset
            if setup.direction == "long":
                hit_sl = bar["low"] <= stop_price
                hit_tp = bar["high"] >= tp_price
            else:
                hit_sl = bar["high"] >= stop_price
                hit_tp = bar["low"] <= tp_price

            if hit_sl:  # empate SL+TP en la misma vela -> SL primero (conservador)
                exit_price, exit_reason, exit_dt, exit_pos = stop_price, "stop_loss", bar["datetime"], pos
                break
            elif hit_tp:
                exit_price, exit_reason, exit_dt, exit_pos = tp_price, "take_profit", bar["datetime"], pos
                break

        if exit_price is None:
            if len(df_slice) == 0:
                continue
            last_bar = df_slice.iloc[-1]
            exit_price = last_bar["close"]
            exit_dt = last_bar["datetime"]
            exit_reason = "time_exit"
            exit_pos = setup.valid_until_pos

        entry_fee_rate = config.MAKER_FEE_PCT if setup.is_limit else config.TAKER_FEE_PCT
        exit_fee_rate = config.TAKER_FEE_PCT

        entry_slippage = entry_price * config.SLIPPAGE_PCT_ESTIMATE
        exit_slippage = exit_price * config.SLIPPAGE_PCT_ESTIMATE

        if setup.direction == "long":
            effective_entry = entry_price + entry_slippage
            effective_exit = exit_price - exit_slippage
            pnl_gross = (effective_exit - effective_entry) * position_size
        else:
            effective_entry = entry_price - entry_slippage
            effective_exit = exit_price + exit_slippage
            pnl_gross = (effective_entry - effective_exit) * position_size

        entry_fee = notional * entry_fee_rate
        exit_fee = (position_size * exit_price) * exit_fee_rate
        fees_paid = entry_fee + exit_fee
        pnl_net = pnl_gross - fees_paid

        capital_before = capital
        capital = capital + pnl_net
        r_multiple = pnl_net / risk_amount if risk_amount > 0 else np.nan

        results.append(TradeResult(
            symbol=setup.symbol, strategy=setup.strategy, direction=setup.direction,
            entry_datetime=setup.signal_datetime, entry_price=entry_price,
            exit_datetime=exit_dt, exit_price=exit_price, exit_reason=exit_reason,
            stop_price=stop_price, take_profit_price=tp_price,
            position_size=position_size, notional=notional,
            fees_paid=fees_paid, pnl_gross=pnl_gross, pnl_net=pnl_net,
            capital_before=capital_before, capital_after=capital, r_multiple=r_multiple,
        ))
        last_exit_pos = exit_pos

    return results


def compute_metrics(results: list, initial_capital: float) -> dict:
    if not results:
        return {"num_trades": 0, "win_rate": np.nan, "profit_factor": np.nan,
                "total_return_pct": 0.0, "max_drawdown_pct": 0.0, "avg_r_multiple": np.nan,
                "final_capital": initial_capital}

    df = pd.DataFrame([r.__dict__ for r in results])
    wins = df[df["pnl_net"] > 0]
    losses = df[df["pnl_net"] <= 0]

    win_rate = len(wins) / len(df) * 100
    gross_profit = wins["pnl_net"].sum()
    gross_loss = abs(losses["pnl_net"].sum())
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else np.inf

    equity_curve = [initial_capital] + df["capital_after"].tolist()
    equity_series = pd.Series(equity_curve)
    running_max = equity_series.cummax()
    drawdown = (equity_series - running_max) / running_max * 100
    max_dd = drawdown.min()

    final_capital = df["capital_after"].iloc[-1]
    total_return_pct = (final_capital - initial_capital) / initial_capital * 100

    return {
        "num_trades": len(df), "win_rate": win_rate, "profit_factor": profit_factor,
        "total_return_pct": total_return_pct, "max_drawdown_pct": max_dd,
        "avg_r_multiple": df["r_multiple"].mean(), "final_capital": final_capital,
        "total_fees": df["fees_paid"].sum(),
    }
