"""
Sweep de sensibilidad para la Estrategia V1: percentil mínimo de swing
(filtra barridos de niveles poco significativos) x ratio TP, sobre los
10 activos. Guarda resultados detallados y un resumen agregado.
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

PERCENTILE_SWEEP = [0, 30, 50, 70]
RR_SWEEP = [1.5, 2.0, 2.5, 3.0]


def load(symbol):
    fname = symbol.replace("/", "_").replace(":", "_")
    df_entry = pd.read_csv(os.path.join(config.DATA_DIR, f"{fname}_{config.TIMEFRAME_ENTRY}.csv"))
    df_context = pd.read_csv(os.path.join(config.DATA_DIR, f"{fname}_{config.TIMEFRAME_CONTEXT}.csv"))
    df_entry["datetime"] = pd.to_datetime(df_entry["datetime"], utc=True)
    df_context["datetime"] = pd.to_datetime(df_context["datetime"], utc=True)
    return df_entry, df_context


def main():
    os.makedirs(config.RESULTS_DIR, exist_ok=True)
    data_cache = {symbol: load(symbol) for symbol in config.SYMBOLS}

    rows = []
    for pct in PERCENTILE_SWEEP:
        for rr in RR_SWEEP:
            config.TP_RR_RATIO = rr
            for symbol in config.SYMBOLS:
                df_entry, df_context = data_cache[symbol]
                setups = generate_setups(symbol, df_context, df_entry, min_swing_percentile=pct)
                results = simulate_trades(setups, df_entry, config.INITIAL_CAPITAL_USDT)
                m = compute_metrics(results, config.INITIAL_CAPITAL_USDT)
                m.update({"symbol": DISPLAY_NAME[symbol], "min_swing_percentile": pct, "tp_rr_ratio": rr})
                rows.append(m)
            print(f"percentile={pct} rr={rr} listo")

    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(config.RESULTS_DIR, "v1_sensitivity_detailed.csv"), index=False)

    agg = df.groupby(["min_swing_percentile", "tp_rr_ratio"]).agg(
        total_trades=("num_trades", "sum"),
        avg_win_rate=("win_rate", "mean"),
        avg_pf=("profit_factor", "mean"),
        avg_return_pct=("total_return_pct", "mean"),
        pct_symbols_profitable=("profit_factor", lambda s: (s > 1).mean() * 100),
    ).reset_index()
    agg.to_csv(os.path.join(config.RESULTS_DIR, "v1_sensitivity_summary.csv"), index=False)
    print("\n" + agg.sort_values("avg_pf", ascending=False).to_string(index=False))


if __name__ == "__main__":
    main()
