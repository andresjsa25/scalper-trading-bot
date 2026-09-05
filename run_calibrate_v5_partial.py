"""
Calibración por símbolo de V5 con el esquema de salida PARCIAL (70% en
1.5R, 30% corre hasta 2R), R:R mínimo exigido al Fibonacci = 1.5,
apalancamiento 50x. SP500 y NASDAQ100 casi no generan setups con R:R>=1.5
en V5 (geometría del Fibonacci ahí no da), así que se dejan fuera de este
barrido -- se usa V1 para esos dos (ver mensaje).
"""
import os
import sys

import pandas as pd

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
import config
from strategy_v5_fib_pullback import generate_setups
from backtest_v5_partial import simulate_partial, compute_metrics

DISPLAY_NAME = {
    "BTC/USDT:USDT": "BTC", "ETH/USDT:USDT": "ETH", "XAUT/USDT:USDT": "XAUT", "SOL/USDT:USDT": "SOL",
    "NCCO1OILBRENT2USD/USDT:USDT": "OIL_BRENT/USD", "NCCOXAG2USD/USDT:USDT": "SILVER/USD",
    "HYPE/USDT:USDT": "HYPE/USD", "NCSKAAPL2USD/USDT:USDT": "AAPL/USD", "NCSKAMZN2USD/USDT:USDT": "AMZN/USD",
}
PERCENTILE_GRID = [0, 20, 30, 40, 50, 60, 70, 80, 90]
MIN_PF = 1.0
MIN_RR = 1.5


def load(symbol):
    fname = symbol.replace("/", "_").replace(":", "_")
    df_entry = pd.read_csv(os.path.join(config.DATA_DIR, f"{fname}_{config.TIMEFRAME_ENTRY}.csv"))
    df_context = pd.read_csv(os.path.join(config.DATA_DIR, f"{fname}_{config.TIMEFRAME_CONTEXT}.csv"))
    df_entry["datetime"] = pd.to_datetime(df_entry["datetime"], utc=True)
    df_context["datetime"] = pd.to_datetime(df_context["datetime"], utc=True)
    return df_entry, df_context


def main():
    os.makedirs(config.RESULTS_DIR, exist_ok=True)
    best_rows = []
    for symbol, name in DISPLAY_NAME.items():
        df_entry, df_context = load(symbol)
        span_days = (df_entry["datetime"].max() - df_entry["datetime"].min()).days
        candidates = []
        for pct in PERCENTILE_GRID:
            setups = generate_setups(symbol, df_context, df_entry, min_swing_percentile=pct, min_rr_ratio=MIN_RR)
            results = simulate_partial(setups, df_entry, config.INITIAL_CAPITAL_USDT)
            m = compute_metrics(results, config.INITIAL_CAPITAL_USDT)
            m.update({"symbol": name, "percentile": pct,
                      "trades_per_day": m["num_trades"] / span_days if span_days else 0})
            candidates.append(m)
        profitable = [c for c in candidates if c["profit_factor"] >= MIN_PF]
        pool = profitable if profitable else candidates
        best = max(pool, key=lambda c: (c["num_trades"] if profitable else c["profit_factor"]))
        best_rows.append(best)
        print(f"{name:15s} pct={best['percentile']:3d} trades={best['num_trades']:4d} "
              f"({best['trades_per_day']:.3f}/día) win_rate={best['win_rate']:.1f}% "
              f"PF={best['profit_factor']:.2f} retorno={best['total_return_pct']:.2f}%")

    df = pd.DataFrame(best_rows)
    df.to_csv(os.path.join(config.RESULTS_DIR, "v5_partial_per_symbol.csv"), index=False)

    total_trades = df["num_trades"].sum()
    total_tpd = df["trades_per_day"].sum()
    total_pnl = (df["final_capital"] - config.INITIAL_CAPITAL_USDT).sum()
    print(f"\nTOTAL V5-parcial (9 activos, sin SP500/NASDAQ100): {total_trades} trades -> "
          f"{total_tpd:.2f} trades/día")
    print(f"PF promedio: {df['profit_factor'].mean():.2f} | rentables: {(df['profit_factor'] >= 1).sum()}/{len(df)} "
          f"| PnL combinado: ${total_pnl:+.2f}")

    # SP500/NASDAQ100 vía V1 (ya calibrados y validados, run_v1_final.py)
    v1_sp500_tpd, v1_nasdaq_tpd = 0.277, 0.341
    print(f"\n+ SP500/USD vía V1: {v1_sp500_tpd}/día | NASDAQ100/USD vía V1: {v1_nasdaq_tpd}/día")
    print(f"TOTAL COMBINADO (V5 parcial x9 + V1 x2): {total_tpd + v1_sp500_tpd + v1_nasdaq_tpd:.2f} trades/día")


if __name__ == "__main__":
    main()
