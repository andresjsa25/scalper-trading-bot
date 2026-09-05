"""
Calibración por símbolo de V1 (igual filosofía que fibo-reversal-bot):
para cada activo, barre percentiles y se queda con el que da MÁS TRADES
sujeto a PF >= 1.0 (frecuencia máxima sin sacrificar rentabilidad).
RR fijo en 2.0 (mejor PF promedio encontrado en el sweep anterior).
"""
import os
import sys

import pandas as pd

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
import config
from strategy_v1_sniper import generate_setups
from backtest import simulate_trades, compute_metrics

DISPLAY_NAME = {
    "BTC/USDT:USDT": "BTC", "ETH/USDT:USDT": "ETH", "XAUT/USDT:USDT": "XAUT",
    "NCSISP5002USD/USDT:USDT": "SP500/USD", "NCSINASDAQ1002USD/USDT:USDT": "NASDAQ100/USD",
    "NCCO1OILBRENT2USD/USDT:USDT": "OIL_BRENT/USD", "NCCOXAG2USD/USDT:USDT": "SILVER/USD",
    "HYPE/USDT:USDT": "HYPE/USD", "NCSKAAPL2USD/USDT:USDT": "AAPL/USD", "NCSKAMZN2USD/USDT:USDT": "AMZN/USD",
}
PERCENTILE_GRID = [0, 20, 30, 40, 50, 60, 70, 80, 90]
MIN_PF = 1.0
config.TP_RR_RATIO = 2.0


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
    all_rows = []

    for symbol in config.SYMBOLS:
        df_entry, df_context = load(symbol)
        span_days = (df_entry["datetime"].max() - df_entry["datetime"].min()).days
        candidates = []
        for pct in PERCENTILE_GRID:
            setups = generate_setups(symbol, df_context, df_entry, min_swing_percentile=pct)
            results = simulate_trades(setups, df_entry, config.INITIAL_CAPITAL_USDT)
            m = compute_metrics(results, config.INITIAL_CAPITAL_USDT)
            m.update({"symbol": DISPLAY_NAME[symbol], "min_swing_percentile": pct,
                      "trades_per_day": m["num_trades"] / span_days if span_days else 0})
            all_rows.append(m)
            candidates.append(m)

        profitable = [c for c in candidates if c["profit_factor"] >= MIN_PF]
        pool = profitable if profitable else candidates  # si ninguno llega a PF>=1, se queda con el mejor PF
        best = max(pool, key=lambda c: (c["num_trades"] if profitable else c["profit_factor"]))
        best_rows.append(best)
        print(f"{DISPLAY_NAME[symbol]:15s} mejor percentil={best['min_swing_percentile']:3d} "
              f"trades={best['num_trades']:4d} ({best['trades_per_day']:.3f}/día) "
              f"win_rate={best['win_rate']:.1f}% PF={best['profit_factor']:.2f} "
              f"retorno={best['total_return_pct']:.2f}%")

    pd.DataFrame(all_rows).to_csv(os.path.join(config.RESULTS_DIR, "v1_per_symbol_all.csv"), index=False)
    best_df = pd.DataFrame(best_rows)
    best_df.to_csv(os.path.join(config.RESULTS_DIR, "v1_per_symbol_best.csv"), index=False)

    total_trades = best_df["num_trades"].sum()
    total_trades_per_day = best_df["trades_per_day"].sum()
    print(f"\nTOTAL portafolio: {total_trades} trades -> {total_trades_per_day:.2f} trades/día combinados "
          f"(objetivo: 3.0)")
    print(f"Símbolos con PF>=1.0: {(best_df['profit_factor'] >= 1.0).sum()}/10")


if __name__ == "__main__":
    main()
