"""
Calibración por símbolo de V5 (mismo criterio que run_calibrate_v1_per_symbol.py):
para cada activo, barre percentiles y se queda con el que da MÁS TRADES
sujeto a PF >= 1.0. Se prueban 2 umbrales de R:R mínimo exigido al
Fibonacci de salida (1.5 y 2.0) para comparar cuál da mejor resultado
combinado. Apalancamiento 50x (LEVERAGE_V5), sin breakeven -- por pedido
del usuario 2026-08-04.
"""
import os
import sys

import pandas as pd

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
import config
from strategy_v5_fib_pullback import generate_setups
from backtest_v5 import simulate_fib_pullback_trades, compute_metrics

DISPLAY_NAME = {
    "BTC/USDT:USDT": "BTC", "ETH/USDT:USDT": "ETH", "XAUT/USDT:USDT": "XAUT", "SOL/USDT:USDT": "SOL",
    "NCSISP5002USD/USDT:USDT": "SP500/USD", "NCSINASDAQ1002USD/USDT:USDT": "NASDAQ100/USD",
    "NCCO1OILBRENT2USD/USDT:USDT": "OIL_BRENT/USD", "NCCOXAG2USD/USDT:USDT": "SILVER/USD",
    "HYPE/USDT:USDT": "HYPE/USD", "NCSKAAPL2USD/USDT:USDT": "AAPL/USD", "NCSKAMZN2USD/USDT:USDT": "AMZN/USD",
}
PERCENTILE_GRID = [0, 20, 30, 40, 50, 60, 70, 80, 90]
MIN_PF = 1.0


def load(symbol):
    fname = symbol.replace("/", "_").replace(":", "_")
    df_entry = pd.read_csv(os.path.join(config.DATA_DIR, f"{fname}_{config.TIMEFRAME_ENTRY}.csv"))
    df_context = pd.read_csv(os.path.join(config.DATA_DIR, f"{fname}_{config.TIMEFRAME_CONTEXT}.csv"))
    df_entry["datetime"] = pd.to_datetime(df_entry["datetime"], utc=True)
    df_context["datetime"] = pd.to_datetime(df_context["datetime"], utc=True)
    return df_entry, df_context


def calibrate(min_rr):
    best_rows = []
    for symbol, name in DISPLAY_NAME.items():
        df_entry, df_context = load(symbol)
        span_days = (df_entry["datetime"].max() - df_entry["datetime"].min()).days
        candidates = []
        for pct in PERCENTILE_GRID:
            setups = generate_setups(symbol, df_context, df_entry, min_swing_percentile=pct, min_rr_ratio=min_rr)
            results = simulate_fib_pullback_trades(setups, df_entry, config.INITIAL_CAPITAL_USDT)
            m = compute_metrics(results, config.INITIAL_CAPITAL_USDT)
            m.update({"symbol": name, "percentile": pct, "trades_per_day": m["num_trades"] / span_days if span_days else 0})
            candidates.append(m)
        profitable = [c for c in candidates if c["profit_factor"] >= MIN_PF]
        pool = profitable if profitable else candidates
        best = max(pool, key=lambda c: (c["num_trades"] if profitable else c["profit_factor"]))
        best_rows.append(best)
        print(f"  {name:15s} pct={best['percentile']:3d} trades={best['num_trades']:4d} "
              f"win_rate={best['win_rate']:.1f}% PF={best['profit_factor']:.2f} retorno={best['total_return_pct']:.2f}%")
    return pd.DataFrame(best_rows)


def main():
    os.makedirs(config.RESULTS_DIR, exist_ok=True)
    for min_rr in [1.5, 2.0]:
        print(f"\n{'=' * 70}\nR:R mínimo exigido = {min_rr}\n{'=' * 70}")
        df = calibrate(min_rr)
        df.to_csv(os.path.join(config.RESULTS_DIR, f"v5_per_symbol_rr{min_rr}.csv"), index=False)
        total_trades = df["num_trades"].sum()
        total_tpd = df["trades_per_day"].sum()
        total_pnl = (df["final_capital"] - config.INITIAL_CAPITAL_USDT).sum()
        print(f"\nTOTAL (R:R>={min_rr}): {total_trades} trades -> {total_tpd:.2f} trades/día combinados")
        print(f"PF promedio: {df['profit_factor'].mean():.2f} | rentables: {(df['profit_factor'] >= 1).sum()}/{len(df)} "
              f"| PnL combinado (11x$1000 aislados): ${total_pnl:+.2f}")


if __name__ == "__main__":
    main()
