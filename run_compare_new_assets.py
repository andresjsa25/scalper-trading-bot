"""
Compara V1 (sniper de liquidez, con el filtro EMA10+T-Theory ya validado
en los 6 activos originales) contra V5 (retroceso Fibonacci) en 3 activos
nuevos pedidos por el usuario (2026-08-04): ADA, LINK, BNB. Config default
para ambas estrategias (percentile=0, sin filtro de tendencia/régimen en
V1, min_rr_ratio=1.5 en V5 -- mismos valores que usan BTC/ETH/SOL en vivo)
porque todavía no hay nada calibrado para estos 3 activos.
"""
import os
import sys

import pandas as pd

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "src", "indicators"))
import config
from strategy_v1_sniper import generate_setups as generate_setups_v1
from strategy_v5_fib_pullback import generate_setups as generate_setups_v5
from backtest import simulate_trades, compute_metrics
from backtest_v5 import simulate_fib_pullback_trades, compute_metrics as compute_metrics_v5
from indicators.trend import add_ema, ema_simple_bias
from indicators.t_theory import detect_base_and_t_window

NEW_SYMBOLS = ["ADA/USDT:USDT", "LINK/USDT:USDT", "BNB/USDT:USDT"]


def load(symbol):
    fname = symbol.replace("/", "_").replace(":", "_")
    dfs = {}
    for tf in ["15m", "1h", "4h"]:
        df = pd.read_csv(os.path.join(config.DATA_DIR, f"{fname}_{tf}.csv"))
        df["datetime"] = pd.to_datetime(df["datetime"], utc=True)
        dfs[tf] = df
    return dfs


def apply_ema10_ttheory_filter(setups, df_entry_indexed):
    kept = []
    for s in setups:
        row = df_entry_indexed.iloc[s.signal_bar_pos]
        required_bias = "up" if s.direction == "long" else "down"
        if row["ema10_bias"] != required_bias:
            continue
        if not bool(row["in_t_window"]):
            continue
        kept.append(s)
    return kept


def run_v1(symbol, dfs):
    config.TP_RR_RATIO = 2.0
    setups = generate_setups_v1(
        symbol, dfs["1h"].copy(), dfs["15m"].copy(), min_swing_percentile=0,
        use_trend_filter=False, use_session_filter=True, require_regime=None,
    )
    df_entry_ind = add_ema(dfs["15m"].copy(), 10, "ema10")
    df_entry_ind["ema10_bias"] = ema_simple_bias(df_entry_ind, "ema10")
    df_entry_ind = detect_base_and_t_window(df_entry_ind)
    filtered = apply_ema10_ttheory_filter(setups, df_entry_ind)

    span_days = (dfs["15m"]["datetime"].max() - dfs["15m"]["datetime"].min()).days or 1
    results = simulate_trades(filtered, dfs["15m"], config.INITIAL_CAPITAL_USDT)
    m = compute_metrics(results, config.INITIAL_CAPITAL_USDT)
    m["span_days"] = span_days
    m["trades_per_day"] = m["num_trades"] / span_days
    return m


def run_v5(symbol, dfs):
    setups = generate_setups_v5(symbol, dfs["4h"].copy(), dfs["1h"].copy(), min_swing_percentile=0, min_rr_ratio=1.5)
    span_days = (dfs["1h"]["datetime"].max() - dfs["1h"]["datetime"].min()).days or 1
    results = simulate_fib_pullback_trades(setups, dfs["1h"], config.INITIAL_CAPITAL_USDT)
    m = compute_metrics_v5(results, config.INITIAL_CAPITAL_USDT)
    m["span_days"] = span_days
    m["trades_per_day"] = m["num_trades"] / span_days
    return m


def main():
    os.makedirs(config.RESULTS_DIR, exist_ok=True)
    rows = []
    for symbol in NEW_SYMBOLS:
        name = symbol.split("/")[0]
        dfs = load(symbol)
        m1 = run_v1(symbol, dfs)
        m5 = run_v5(symbol, dfs)
        winner = "V1" if (m1["profit_factor"] or 0) >= (m5["profit_factor"] or 0) else "V5"
        rows.append({
            "symbol": name,
            "v1_trades": m1["num_trades"], "v1_tpd": m1["trades_per_day"], "v1_pf": m1["profit_factor"],
            "v1_return": m1["total_return_pct"], "v1_dd": m1["max_drawdown_pct"],
            "v5_trades": m5["num_trades"], "v5_tpd": m5["trades_per_day"], "v5_pf": m5["profit_factor"],
            "v5_return": m5["total_return_pct"], "v5_dd": m5["max_drawdown_pct"],
            "winner": winner,
        })
        print(f"{name:6s} || V1(EMA10+T) trades={m1['num_trades']:3d} tpd={m1['trades_per_day']:.3f} "
              f"PF={m1['profit_factor']:.2f} ret={m1['total_return_pct']:6.2f}% DD={m1['max_drawdown_pct']:6.2f}% "
              f"|| V5 trades={m5['num_trades']:3d} tpd={m5['trades_per_day']:.3f} "
              f"PF={m5['profit_factor']:.2f} ret={m5['total_return_pct']:6.2f}% DD={m5['max_drawdown_pct']:6.2f}% "
              f"|| GANADOR: {winner}")

    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(config.RESULTS_DIR, "v1_vs_v5_new_assets.csv"), index=False)


if __name__ == "__main__":
    main()
