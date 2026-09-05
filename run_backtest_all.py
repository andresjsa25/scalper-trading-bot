"""Corre las 3 estrategias (V1/V2/V3) sobre los 10 activos y arma la tabla comparativa."""
import os
import sys

import pandas as pd

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
import config
from backtest import simulate_trades, compute_metrics
import strategy_v1_sniper
import strategy_v2_liquidity_swift
import strategy_v3_crt

DISPLAY_NAME = {
    "BTC/USDT:USDT": "BTC", "ETH/USDT:USDT": "ETH", "XAUT/USDT:USDT": "XAUT",
    "NCSISP5002USD/USDT:USDT": "SP500/USD", "NCSINASDAQ1002USD/USDT:USDT": "NASDAQ100/USD",
    "NCCO1OILBRENT2USD/USDT:USDT": "OIL_BRENT/USD", "NCCOXAG2USD/USDT:USDT": "SILVER/USD",
    "HYPE/USDT:USDT": "HYPE/USD", "NCSKAAPL2USD/USDT:USDT": "AAPL/USD", "NCSKAMZN2USD/USDT:USDT": "AMZN/USD",
}

STRATEGIES = {
    "v1_sniper": strategy_v1_sniper,
    "v2_liquidity_swift": strategy_v2_liquidity_swift,
    "v3_crt": strategy_v3_crt,
}


def load(symbol):
    fname = symbol.replace("/", "_").replace(":", "_")
    df_entry = pd.read_csv(os.path.join(config.DATA_DIR, f"{fname}_{config.TIMEFRAME_ENTRY}.csv"))
    df_context = pd.read_csv(os.path.join(config.DATA_DIR, f"{fname}_{config.TIMEFRAME_CONTEXT}.csv"))
    df_entry["datetime"] = pd.to_datetime(df_entry["datetime"], utc=True)
    df_context["datetime"] = pd.to_datetime(df_context["datetime"], utc=True)
    return df_entry, df_context


def main():
    os.makedirs(config.RESULTS_DIR, exist_ok=True)
    rows = []

    for strat_name, mod in STRATEGIES.items():
        print(f"\n{'=' * 70}\n{strat_name}\n{'=' * 70}")
        for symbol in config.SYMBOLS:
            fname = symbol.replace("/", "_").replace(":", "_")
            path_entry = os.path.join(config.DATA_DIR, f"{fname}_{config.TIMEFRAME_ENTRY}.csv")
            if not os.path.exists(path_entry):
                print(f"[!] Sin datos todavía para {symbol}, se salta")
                continue
            df_entry, df_context = load(symbol)
            setups = mod.generate_setups(symbol, df_context, df_entry)
            results = simulate_trades(setups, df_entry, config.INITIAL_CAPITAL_USDT)
            metrics = compute_metrics(results, config.INITIAL_CAPITAL_USDT)
            metrics["symbol"] = symbol
            metrics["display_name"] = DISPLAY_NAME.get(symbol, symbol)
            metrics["strategy"] = strat_name
            rows.append(metrics)
            print(f"  {DISPLAY_NAME.get(symbol, symbol):15s} setups={len(setups):4d} "
                  f"trades={metrics['num_trades']:4d} win_rate={metrics['win_rate']:.1f}% "
                  f"PF={metrics['profit_factor']:.2f} retorno={metrics['total_return_pct']:.2f}%")

    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(config.RESULTS_DIR, "all_strategies_summary.csv"), index=False)

    print("\n" + "=" * 70 + "\nRESUMEN POR ESTRATEGIA (agregado de los 10 activos)\n" + "=" * 70)
    agg = df.groupby("strategy").agg(
        total_trades=("num_trades", "sum"),
        avg_win_rate=("win_rate", "mean"),
        avg_profit_factor=("profit_factor", "mean"),
        avg_return_pct=("total_return_pct", "mean"),
    )
    print(agg.to_string())
    print("\nGuardado en results/all_strategies_summary.csv")


if __name__ == "__main__":
    main()
