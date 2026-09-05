"""
Backtest de src/strategy_v9_bb_rsi_confluence.py sobre los 10 símbolos de
config.SYMBOLS, barriendo rr_ratio. Mismo motor de costos/riesgo que V1
(src/backtest.py) para que los resultados sean comparables contra
results/v1_final_summary.csv.
"""
import os
import sys

import pandas as pd

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
import config
from strategy_v9_bb_rsi_confluence import generate_setups
from backtest import simulate_trades, compute_metrics

DISPLAY = {
    "BTC/USDT:USDT": "BTC", "ETH/USDT:USDT": "ETH", "XAUT/USDT:USDT": "XAUT",
    "NCSISP5002USD/USDT:USDT": "SP500/USD", "NCSINASDAQ1002USD/USDT:USDT": "NASDAQ100/USD",
    "NCCO1OILBRENT2USD/USDT:USDT": "OIL_BRENT/USD", "NCCOXAG2USD/USDT:USDT": "SILVER/USD",
    "HYPE/USDT:USDT": "HYPE", "NCSKAAPL2USD/USDT:USDT": "AAPL/USD", "NCSKAMZN2USD/USDT:USDT": "AMZN/USD",
}
RR_RATIOS = [1.0, 1.3, 1.5, 1.8, 2.0]


def load_df(symbol: str, tf: str) -> pd.DataFrame:
    fname = symbol.replace("/", "_").replace(":", "_")
    path = os.path.join(config.DATA_DIR, f"{fname}_{tf}.csv")
    df = pd.read_csv(path)
    df["datetime"] = pd.to_datetime(df["datetime"], utc=True)
    return df


def main():
    os.makedirs(config.RESULTS_DIR, exist_ok=True)
    rows, trade_rows = [], []

    for symbol in config.SYMBOLS:
        df_4h = load_df(symbol, "4h")
        df_1h = load_df(symbol, "1h")
        display = DISPLAY.get(symbol, symbol)
        days_span = (df_1h["datetime"].iloc[-1] - df_1h["datetime"].iloc[0]).total_seconds() / 86400

        for rr in RR_RATIOS:
            setups = generate_setups(symbol, df_4h, df_1h, rr_ratio=rr)
            results = simulate_trades(setups, df_1h, config.INITIAL_CAPITAL_USDT)
            metrics = compute_metrics(results, config.INITIAL_CAPITAL_USDT)
            rows.append({
                "symbol": display, "rr_ratio": rr, "num_trades": metrics["num_trades"],
                "win_rate": metrics["win_rate"], "profit_factor": metrics["profit_factor"],
                "total_return_pct": metrics["total_return_pct"], "max_drawdown_pct": metrics["max_drawdown_pct"],
                "avg_r_multiple": metrics["avg_r_multiple"],
                "trades_per_day": metrics["num_trades"] / days_span if days_span > 0 else 0,
                "days_analizados": round(days_span, 1), "total_fees": metrics.get("total_fees", 0),
            })
            for r in results:
                trade_rows.append({"symbol": display, "rr_ratio": rr, "entry_datetime": r.entry_datetime,
                                    "direction": r.direction, "pnl_net": r.pnl_net, "r_multiple": r.r_multiple,
                                    "exit_reason": r.exit_reason})
        print(f"{display:16s} listo ({days_span:.0f} días)")

    df_summary = pd.DataFrame(rows)
    df_summary.to_csv(os.path.join(config.RESULTS_DIR, "v9_bb_rsi_summary.csv"), index=False)
    df_trades = pd.DataFrame(trade_rows)
    df_trades.to_csv(os.path.join(config.RESULTS_DIR, "v9_bb_rsi_trades_detail.csv"), index=False)

    print("\n=== Resumen por símbolo y rr_ratio ===")
    print(df_summary.to_string(index=False))

    agg_rows = []
    for rr, grp in df_trades.groupby("rr_ratio"):
        wins = grp[grp["pnl_net"] > 0]
        losses = grp[grp["pnl_net"] <= 0]
        pf = wins["pnl_net"].sum() / abs(losses["pnl_net"].sum()) if losses["pnl_net"].sum() != 0 else float("inf")
        symbols_profitable = grp.groupby("symbol")["pnl_net"].sum().gt(0).sum()
        agg_rows.append({
            "rr_ratio": rr, "total_trades": len(grp),
            "win_rate": round(len(wins) / len(grp) * 100, 1) if len(grp) else 0,
            "profit_factor": round(pf, 2), "pnl_net_total": round(grp["pnl_net"].sum(), 2),
            "symbols_profitable": f"{symbols_profitable}/{grp['symbol'].nunique()}",
        })
    df_agg = pd.DataFrame(agg_rows).sort_values("profit_factor", ascending=False)
    df_agg.to_csv(os.path.join(config.RESULTS_DIR, "v9_bb_rsi_aggregate.csv"), index=False)
    print("\n=== Agregado por rr_ratio ===")
    print(df_agg.to_string(index=False))


if __name__ == "__main__":
    main()
