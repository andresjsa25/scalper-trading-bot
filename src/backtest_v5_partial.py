"""
Motor de backtest V5 con toma de beneficios PARCIAL: 70% de la posición
cierra en 1.5R, el 30% restante corre hasta 2R (R = distancia de riesgo
entrada-stop). Mismo stop para ambas porciones (sin breakeven, por pedido
del usuario). Separado de backtest_v5.py (TP único) para comparar los dos
esquemas sin romper nada de lo ya calibrado.
"""
import os
import sys
from dataclasses import dataclass

import numpy as np
import pandas as pd

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from backtest_v5 import LEVERAGE_V5

PORTION_1_PCT = 0.70   # cierra en TP1
PORTION_2_PCT = 0.30   # corre hasta TP2
TP1_R_MULTIPLE = 1.5
TP2_R_MULTIPLE = 2.0


@dataclass
class PartialTradeResult:
    symbol: str
    direction: str
    entry_datetime: pd.Timestamp
    entry_price: float
    stop_price: float
    tp1_price: float
    tp2_price: float
    exit1_datetime: pd.Timestamp
    exit1_price: float
    exit1_reason: str      # 'tp1', 'stop_loss', 'time_exit'
    exit2_datetime: pd.Timestamp
    exit2_price: float
    exit2_reason: str      # 'tp2', 'stop_loss', 'time_exit'
    position_size: float
    notional: float
    fees_paid: float
    pnl_net: float
    capital_before: float
    capital_after: float
    r_multiple: float


def simulate_partial(setups: list, df_entry: pd.DataFrame, initial_capital: float,
                      leverage: float = LEVERAGE_V5) -> list:
    results = []
    capital = initial_capital
    setups_sorted = sorted(setups, key=lambda s: s.signal_bar_pos)
    last_exit_pos = -1

    for setup in setups_sorted:
        if setup.signal_bar_pos <= last_exit_pos:
            continue

        entry_price = setup.entry_price_target
        stop_price = setup.stop_price
        risk_per_unit = abs(entry_price - stop_price)

        stop_distance_pct = risk_per_unit / entry_price
        liq_buffer = (1 / leverage) - 0.004
        if stop_distance_pct >= liq_buffer:
            continue

        if setup.direction == "long":
            tp1_price = entry_price + risk_per_unit * TP1_R_MULTIPLE
            tp2_price = entry_price + risk_per_unit * TP2_R_MULTIPLE
        else:
            tp1_price = entry_price - risk_per_unit * TP1_R_MULTIPLE
            tp2_price = entry_price - risk_per_unit * TP2_R_MULTIPLE

        risk_amount = capital * setup.risk_pct
        position_size = risk_amount / risk_per_unit
        notional = position_size * entry_price
        margin_required = notional / leverage
        if margin_required > capital:
            position_size = (capital * leverage) / entry_price
            notional = position_size * entry_price

        size1 = position_size * PORTION_1_PCT
        size2 = position_size * PORTION_2_PCT

        df_slice = df_entry.iloc[setup.signal_bar_pos: setup.valid_until_pos + 1]

        p1_open, p2_open = True, True
        exit1 = exit2 = None
        last_bar_seen = None

        for offset, (_, bar) in enumerate(df_slice.iterrows()):
            pos = setup.signal_bar_pos + offset
            last_bar_seen = bar
            if setup.direction == "long":
                hit_sl = bar["low"] <= stop_price
                hit_tp1 = bar["high"] >= tp1_price
                hit_tp2 = bar["high"] >= tp2_price
            else:
                hit_sl = bar["high"] >= stop_price
                hit_tp1 = bar["low"] <= tp1_price
                hit_tp2 = bar["low"] <= tp2_price

            if hit_sl:
                if p1_open:
                    exit1 = (stop_price, "stop_loss", bar["datetime"])
                    p1_open = False
                if p2_open:
                    exit2 = (stop_price, "stop_loss", bar["datetime"])
                    p2_open = False
                break

            if p1_open and hit_tp1:
                exit1 = (tp1_price, "tp1", bar["datetime"])
                p1_open = False

            if p2_open and hit_tp2:
                exit2 = (tp2_price, "tp2", bar["datetime"])
                p2_open = False

            if not p1_open and not p2_open:
                break

        if p1_open or p2_open:
            if last_bar_seen is None:
                continue
            if p1_open:
                exit1 = (last_bar_seen["close"], "time_exit", last_bar_seen["datetime"])
            if p2_open:
                exit2 = (last_bar_seen["close"], "time_exit", last_bar_seen["datetime"])

        entry_fee_rate = config.TAKER_FEE_PCT
        exit_fee_rate = config.TAKER_FEE_PCT
        entry_slippage = entry_price * config.SLIPPAGE_PCT_ESTIMATE

        def leg_pnl(exit_price, size):
            exit_slip = exit_price * config.SLIPPAGE_PCT_ESTIMATE
            if setup.direction == "long":
                eff_entry = entry_price + entry_slippage
                eff_exit = exit_price - exit_slip
                gross = (eff_exit - eff_entry) * size
            else:
                eff_entry = entry_price - entry_slippage
                eff_exit = exit_price + exit_slip
                gross = (eff_entry - eff_exit) * size
            fee = (size * exit_price) * exit_fee_rate
            return gross - fee

        pnl1 = leg_pnl(exit1[0], size1)
        pnl2 = leg_pnl(exit2[0], size2)
        entry_fee = notional * entry_fee_rate
        pnl_net = pnl1 + pnl2 - entry_fee
        fees_paid = entry_fee + (size1 * exit1[0]) * exit_fee_rate + (size2 * exit2[0]) * exit_fee_rate

        capital_before = capital
        capital = capital + pnl_net
        r_multiple = pnl_net / risk_amount if risk_amount > 0 else np.nan

        results.append(PartialTradeResult(
            symbol=setup.symbol, direction=setup.direction,
            entry_datetime=setup.signal_datetime, entry_price=entry_price,
            stop_price=stop_price, tp1_price=tp1_price, tp2_price=tp2_price,
            exit1_datetime=exit1[2], exit1_price=exit1[0], exit1_reason=exit1[1],
            exit2_datetime=exit2[2], exit2_price=exit2[0], exit2_reason=exit2[1],
            position_size=position_size, notional=notional, fees_paid=fees_paid,
            pnl_net=pnl_net, capital_before=capital_before, capital_after=capital,
            r_multiple=r_multiple,
        ))
        last_exit_pos = setup.signal_bar_pos + max(
            df_entry["datetime"].searchsorted(exit1[2]) - setup.signal_bar_pos,
            df_entry["datetime"].searchsorted(exit2[2]) - setup.signal_bar_pos,
        )

    return results


def compute_metrics(results: list, initial_capital: float) -> dict:
    if not results:
        return {"num_trades": 0, "win_rate": np.nan, "profit_factor": np.nan,
                "total_return_pct": 0.0, "max_drawdown_pct": 0.0, "final_capital": initial_capital}

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
        "final_capital": final_capital, "total_fees": df["fees_paid"].sum(),
    }
