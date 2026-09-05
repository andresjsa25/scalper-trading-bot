"""Backtest de la Estrategia V1 (Sniper de liquidez) en los 10 activos, 15min/1h."""
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
    for symbol in config.SYMBOLS:
        fname = symbol.replace("/", "_").replace(":", "_")
        path_entry = os.path.join(config.DATA_DIR, f"{fname}_{config.TIMEFRAME_ENTRY}.csv")
        if not os.path.exists(path_entry):
            print(f"[!] Sin datos todavía para {symbol}, se salta")
            continue
        df_entry, df_context = load(symbol)
        setups = generate_setups(symbol, df_context, df_entry)
        results = simulate_trades(setups, df_entry, config.INITIAL_CAPITAL_USDT)
        metrics = compute_metrics(results, config.INITIAL_CAPITAL_USDT)
        metrics["symbol"] = symbol
        metrics["display_name"] = DISPLAY_NAME.get(symbol, symbol)
        rows.append(metrics)
        print(f"{DISPLAY_NAME.get(symbol, symbol):15s} setups={len(setups):4d} "
              f"trades={metrics['num_trades']:4d} win_rate={metrics['win_rate']:.1f}% "
              f"PF={metrics['profit_factor']:.2f} retorno={metrics['total_return_pct']:.2f}%")

    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(config.RESULTS_DIR, "v1_sniper_summary.csv"), index=False)
    print("\nGuardado en results/v1_sniper_summary.csv")


if __name__ == "__main__":
    main()
