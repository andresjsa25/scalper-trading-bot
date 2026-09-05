"""
Backtest de src/strategy_v7_confluence.py sobre los mismos 10 símbolos de
config.SYMBOLS (los que corren hoy en V1 en vivo), barriendo 4 ratios TP
(1.5, 2.0, 2.3, 2.5). Reutiliza el motor de backtest existente (src/backtest.py:
simulate_trades + compute_metrics -- mismo modelo de comisiones/slippage/
liquidación que ya usa V1) para que los resultados sean directamente
comparables contra results/v1_final_summary.csv.

Standalone, de solo lectura sobre data/, escribe únicamente en results/.
No importa ni ejecuta nada de run_live_trading.py / live_trading.py.
"""
import os
import sys

import pandas as pd

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
import config
from strategy_v7_confluence import generate_setups
from backtest import simulate_trades, compute_metrics

DISPLAY = {
    "BTC/USDT:USDT": "BTC", "ETH/USDT:USDT": "ETH", "XAUT/USDT:USDT": "XAUT",
    "NCSISP5002USD/USDT:USDT": "SP500/USD", "NCSINASDAQ1002USD/USDT:USDT": "NASDAQ100/USD",
    "NCCO1OILBRENT2USD/USDT:USDT": "OIL_BRENT/USD", "NCCOXAG2USD/USDT:USDT": "SILVER/USD",
    "HYPE/USDT:USDT": "HYPE", "NCSKAAPL2USD/USDT:USDT": "AAPL/USD", "NCSKAMZN2USD/USDT:USDT": "AMZN/USD",
}
RR_RATIOS = [1.5, 2.0, 2.3, 2.5]


def load_df(symbol: str, tf: str) -> pd.DataFrame:
    fname = symbol.replace("/", "_").replace(":", "_")
    path = os.path.join(config.DATA_DIR, f"{fname}_{tf}.csv")
    df = pd.read_csv(path)
    df["datetime"] = pd.to_datetime(df["datetime"], utc=True)
    return df


def main():
    os.makedirs(config.RESULTS_DIR, exist_ok=True)
    rows = []
    trade_rows = []

    for symbol in config.SYMBOLS:
        try:
            df_4h = load_df(symbol, "4h")
            df_1h = load_df(symbol, "1h")
            df_15m = load_df(symbol, "15m")
        except FileNotFoundError as e:
            print(f"[!] {symbol}: falta un archivo de datos ({e}), se salta.")
            continue
        if len(df_15m) == 0 or len(df_1h) == 0 or len(df_4h) == 0:
            print(f"[!] {symbol}: algún timeframe está vacío, se salta.")
            continue

        days_span = (df_15m["datetime"].iloc[-1] - df_15m["datetime"].iloc[0]).total_seconds() / 86400
        display = DISPLAY.get(symbol, symbol)

        for rr in RR_RATIOS:
            setups = generate_setups(symbol, df_4h, df_1h, df_15m, rr_ratio=rr)
            results = simulate_trades(setups, df_15m, config.INITIAL_CAPITAL_USDT)
            metrics = compute_metrics(results, config.INITIAL_CAPITAL_USDT)

            trades_per_day = metrics["num_trades"] / days_span if days_span > 0 else 0
            rows.append({
                "symbol": display, "rr_ratio": rr,
                "num_trades": metrics["num_trades"], "win_rate": metrics["win_rate"],
                "profit_factor": metrics["profit_factor"], "total_return_pct": metrics["total_return_pct"],
                "max_drawdown_pct": metrics["max_drawdown_pct"], "avg_r_multiple": metrics["avg_r_multiple"],
                "trades_per_day": trades_per_day, "days_analizados": round(days_span, 1),
                "total_fees": metrics.get("total_fees", 0),
            })

            for r in results:
                trade_rows.append({
                    "symbol": display, "rr_ratio": rr, "entry_datetime": r.entry_datetime,
                    "direction": r.direction, "pnl_net": r.pnl_net, "r_multiple": r.r_multiple,
                    "exit_reason": r.exit_reason,
                })

        print(f"{display:16s} listo ({days_span:.0f} días de datos en 15m)")

    df_summary = pd.DataFrame(rows)
    df_summary.to_csv(os.path.join(config.RESULTS_DIR, "v7_confluence_summary.csv"), index=False)

    df_trades = pd.DataFrame(trade_rows)
    df_trades.to_csv(os.path.join(config.RESULTS_DIR, "v7_confluence_trades_detail.csv"), index=False)

    # --- agregado por rr_ratio, across todos los símbolos ---
    agg_rows = []
    if len(df_trades):
        for rr, grp in df_trades.groupby("rr_ratio"):
            wins = grp[grp["pnl_net"] > 0]
            losses = grp[grp["pnl_net"] <= 0]
            gross_profit = wins["pnl_net"].sum()
            gross_loss = abs(losses["pnl_net"].sum())
            pf = gross_profit / gross_loss if gross_loss > 0 else float("inf")
            win_rate = len(wins) / len(grp) * 100 if len(grp) else 0
            symbols_profitable = grp.groupby("symbol")["pnl_net"].sum().gt(0).sum()
            symbols_total = grp["symbol"].nunique()
            agg_rows.append({
                "rr_ratio": rr, "total_trades": len(grp), "win_rate": round(win_rate, 1),
                "profit_factor": round(pf, 2), "pnl_net_total": round(grp["pnl_net"].sum(), 2),
                "symbols_profitable": f"{symbols_profitable}/{symbols_total}",
            })
    df_agg = pd.DataFrame(agg_rows).sort_values("profit_factor", ascending=False) if agg_rows else pd.DataFrame()
    df_agg.to_csv(os.path.join(config.RESULTS_DIR, "v7_confluence_aggregate.csv"), index=False)

    print("\n=== AGREGADO por rr_ratio -- ordenado por profit factor ===")
    if len(df_agg):
        print(df_agg.to_string(index=False))
    else:
        print("(sin operaciones generadas -- ver nota más abajo)")
    print("\nGuardado en results/v7_confluence_summary.csv, "
          "results/v7_confluence_aggregate.csv y results/v7_confluence_trades_detail.csv")


if __name__ == "__main__":
    main()
