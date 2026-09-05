"""TP único (Fibonacci), compara R:R mínimo exigido 1.5 / 1.75 / 2.0,
calibrando percentil por símbolo, solo para los 6 activos asignados a V5:
AAPL, HYPE, BTC, SILVER, ETH, SOL."""
import os
import sys

import pandas as pd

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
import config
from strategy_v5_fib_pullback import generate_setups
from backtest_v5 import simulate_fib_pullback_trades, compute_metrics

DISPLAY_NAME = {
    "BTC/USDT:USDT": "BTC", "ETH/USDT:USDT": "ETH", "SOL/USDT:USDT": "SOL",
    "NCCOXAG2USD/USDT:USDT": "SILVER/USD", "HYPE/USDT:USDT": "HYPE/USD", "NCSKAAPL2USD/USDT:USDT": "AAPL/USD",
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
    rows = []
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
        rows.append(best)
        print(f"  {name:15s} pct={best['percentile']:3d} trades={best['num_trades']:4d} "
              f"({best['trades_per_day']:.3f}/día) win_rate={best['win_rate']:.1f}% PF={best['profit_factor']:.2f} "
              f"retorno={best['total_return_pct']:.2f}%")
    return pd.DataFrame(rows)


def main():
    os.makedirs(config.RESULTS_DIR, exist_ok=True)
    for min_rr in [1.5, 1.75, 2.0]:
        print(f"\n{'=' * 70}\nR:R mínimo = {min_rr}\n{'=' * 70}")
        df = calibrate(min_rr)
        df.to_csv(os.path.join(config.RESULTS_DIR, f"v5_final6_rr{min_rr}.csv"), index=False)
        total_trades = df["num_trades"].sum()
        total_tpd = df["trades_per_day"].sum()
        total_pnl = (df["final_capital"] - config.INITIAL_CAPITAL_USDT).sum()
        print(f"TOTAL: {total_trades} trades -> {total_tpd:.2f}/día | PF promedio: {df['profit_factor'].mean():.2f} "
              f"| rentables: {(df['profit_factor'] >= 1).sum()}/{len(df)} | PnL combinado: ${total_pnl:+.2f}")


if __name__ == "__main__":
    main()
