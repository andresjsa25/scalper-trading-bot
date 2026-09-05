"""
Backtest de src/strategy_sanchezzfx.py sobre los 13 activos live, barriendo
4 tipos de nivel (asia/london/newyork/prevday) x 4 ratios TP (1:1, 1.5:1,
2:1, 2.3:1) = 208 combinaciones. Reutiliza el motor de backtest existente
(src/backtest.py: simulate_trades + compute_metrics -- mismo modelo de
comisiones/slippage/liquidación que ya se usa para V1/V2, sin modificarlo)
para que los resultados sean comparables entre estrategias.

No importa ni ejecuta nada de run_live_trading.py / live_trading.py.
Standalone, de solo lectura sobre data/, escribe únicamente en results/.
"""
import os
import sys
from collections import defaultdict

import pandas as pd

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
import config
from strategy_sanchezzfx import generate_setups, LEVEL_TYPES
from backtest import simulate_trades, compute_metrics

SYMBOLS = [
    "NCCOXAG2USD/USDT:USDT", "NCSISP5002USD/USDT:USDT", "NCSINASDAQ1002USD/USDT:USDT",
    "NCCO1OILBRENT2USD/USDT:USDT", "XAUT/USDT:USDT", "NCSKAMZN2USD/USDT:USDT",
    "ADA/USDT:USDT", "BNB/USDT:USDT", "NCSKAAPL2USD/USDT:USDT",
    "ETH/USDT:USDT", "HYPE/USDT:USDT", "SOL/USDT:USDT", "BTC/USDT:USDT",
]
DISPLAY = {
    "NCCOXAG2USD/USDT:USDT": "SILVER/USD", "NCSISP5002USD/USDT:USDT": "SP500/USD",
    "NCSINASDAQ1002USD/USDT:USDT": "NASDAQ100/USD", "NCCO1OILBRENT2USD/USDT:USDT": "OIL_BRENT/USD",
    "XAUT/USDT:USDT": "XAUT", "NCSKAMZN2USD/USDT:USDT": "AMZN/USD",
    "ADA/USDT:USDT": "ADA", "BNB/USDT:USDT": "BNB", "NCSKAAPL2USD/USDT:USDT": "AAPL/USD",
    "ETH/USDT:USDT": "ETH", "HYPE/USDT:USDT": "HYPE", "SOL/USDT:USDT": "SOL", "BTC/USDT:USDT": "BTC",
}
RR_RATIOS = [1.0, 1.5, 2.0, 2.3]


def load_df(symbol: str, tf: str) -> pd.DataFrame:
    fname = symbol.replace("/", "_").replace(":", "_")
    path = os.path.join(config.DATA_DIR, f"{fname}_{tf}.csv")
    df = pd.read_csv(path)
    df["datetime"] = pd.to_datetime(df["datetime"], utc=True)
    return df


def main():
    os.makedirs(config.RESULTS_DIR, exist_ok=True)
    rows = []
    trade_rows = []  # detalle de cada trade, para el análisis de consistencia después

    for symbol in SYMBOLS:
        try:
            df_4h = load_df(symbol, "4h")
            df_1h = load_df(symbol, "1h")
            df_5m = load_df(symbol, "5m")
        except FileNotFoundError as e:
            print(f"[!] {symbol}: falta un archivo de datos ({e}), se salta.")
            continue
        if len(df_5m) == 0 or len(df_1h) == 0 or len(df_4h) == 0:
            print(f"[!] {symbol}: algún timeframe está vacío, se salta.")
            continue

        days_span = (df_5m["datetime"].iloc[-1] - df_5m["datetime"].iloc[0]).total_seconds() / 86400

        for level_type in LEVEL_TYPES:
            for rr in RR_RATIOS:
                setups = generate_setups(symbol, df_4h, df_1h, df_5m, level_type=level_type, rr_ratio=rr)
                results = simulate_trades(setups, df_5m, config.INITIAL_CAPITAL_USDT)
                metrics = compute_metrics(results, config.INITIAL_CAPITAL_USDT)

                trades_per_day = metrics["num_trades"] / days_span if days_span > 0 else 0
                rows.append({
                    "symbol": DISPLAY.get(symbol, symbol), "level_type": level_type, "rr_ratio": rr,
                    "num_trades": metrics["num_trades"], "win_rate": metrics["win_rate"],
                    "profit_factor": metrics["profit_factor"], "total_return_pct": metrics["total_return_pct"],
                    "max_drawdown_pct": metrics["max_drawdown_pct"], "avg_r_multiple": metrics["avg_r_multiple"],
                    "trades_per_day": trades_per_day, "days_analizados": round(days_span, 1),
                    "total_fees": metrics.get("total_fees", 0),
                })

                for r in results:
                    trade_rows.append({
                        "symbol": DISPLAY.get(symbol, symbol), "level_type": level_type, "rr_ratio": rr,
                        "entry_datetime": r.entry_datetime, "direction": r.direction,
                        "pnl_net": r.pnl_net, "r_multiple": r.r_multiple, "exit_reason": r.exit_reason,
                    })

        print(f"{DISPLAY.get(symbol, symbol):16s} listo ({days_span:.0f} días de datos)")

    df_summary = pd.DataFrame(rows)
    df_summary.to_csv(os.path.join(config.RESULTS_DIR, "sanchezzfx_sweep_by_symbol.csv"), index=False)

    df_trades = pd.DataFrame(trade_rows)
    df_trades.to_csv(os.path.join(config.RESULTS_DIR, "sanchezzfx_trades_detail.csv"), index=False)

    # --- agregado por (level_type, rr_ratio) across todos los símbolos ---
    agg_rows = []
    for (level_type, rr), grp in df_trades.groupby(["level_type", "rr_ratio"]):
        wins = grp[grp["pnl_net"] > 0]
        losses = grp[grp["pnl_net"] <= 0]
        gross_profit = wins["pnl_net"].sum()
        gross_loss = abs(losses["pnl_net"].sum())
        pf = gross_profit / gross_loss if gross_loss > 0 else float("inf")
        win_rate = len(wins) / len(grp) * 100 if len(grp) else 0
        symbols_profitable = grp.groupby("symbol")["pnl_net"].sum().gt(0).sum()
        symbols_total = grp["symbol"].nunique()
        agg_rows.append({
            "level_type": level_type, "rr_ratio": rr, "total_trades": len(grp),
            "win_rate": round(win_rate, 1), "profit_factor": round(pf, 2),
            "pnl_net_total": round(grp["pnl_net"].sum(), 2),
            "symbols_profitable": f"{symbols_profitable}/{symbols_total}",
        })
    df_agg = pd.DataFrame(agg_rows).sort_values("profit_factor", ascending=False)
    df_agg.to_csv(os.path.join(config.RESULTS_DIR, "sanchezzfx_sweep_aggregate.csv"), index=False)

    print("\n=== AGREGADO por (nivel, ratio) -- ordenado por profit factor ===")
    print(df_agg.to_string(index=False))
    print("\nGuardado en results/sanchezzfx_sweep_by_symbol.csv, "
          "results/sanchezzfx_sweep_aggregate.csv y results/sanchezzfx_trades_detail.csv")


if __name__ == "__main__":
    main()
