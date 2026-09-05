"""
Backtest de la Estrategia V6 ("order flow proxy", ver docstring en
src/strategy_v6_orderflow_proxy.py -- NO es la estrategia real del video,
es una aproximación con las únicas reglas cuantificables que dio) sobre 6
activos elegidos al azar del bot, últimos 3 meses, 5min (se descargó el
histórico de 5m para BNB/ETH/HYPE que no lo tenían, 2026-08-05).
"""
import os
import sys

import pandas as pd

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
import config
from strategy_v6_orderflow_proxy import generate_setups
from backtest import simulate_trades, compute_metrics

SYMBOLS = [
    "NCSKAMZN2USD/USDT:USDT",       # Amazon -- elegido al azar
    "NCSISP5002USD/USDT:USDT",      # SP500 -- elegido al azar
    "HYPE/USDT:USDT",               # elegido al azar
    "BNB/USDT:USDT",                # elegido al azar
    "ETH/USDT:USDT",                # elegido al azar
    "NCSINASDAQ1002USD/USDT:USDT",  # Nasdaq100 -- elegido al azar
]
DISPLAY_NAME = {
    "NCSKAMZN2USD/USDT:USDT": "AMZN/USD", "NCSISP5002USD/USDT:USDT": "SP500/USD",
    "HYPE/USDT:USDT": "HYPE/USD", "BNB/USDT:USDT": "BNB/USD",
    "ETH/USDT:USDT": "ETH/USD", "NCSINASDAQ1002USD/USDT:USDT": "NASDAQ100/USD",
}
TIMEFRAME = "5m"
BACKTEST_DAYS = 90  # 3 meses, según lo pedido -- no 1.5 años como el resto del bot


def load(symbol: str) -> pd.DataFrame:
    fname = symbol.replace("/", "_").replace(":", "_")
    df = pd.read_csv(os.path.join(config.DATA_DIR, f"{fname}_{TIMEFRAME}.csv"))
    df["datetime"] = pd.to_datetime(df["datetime"], utc=True)
    cutoff = df["datetime"].max() - pd.Timedelta(days=BACKTEST_DAYS)
    return df[df["datetime"] >= cutoff].reset_index(drop=True)


def main():
    os.makedirs(config.RESULTS_DIR, exist_ok=True)
    rows = []

    for symbol in SYMBOLS:
        fname = symbol.replace("/", "_").replace(":", "_")
        path = os.path.join(config.DATA_DIR, f"{fname}_{TIMEFRAME}.csv")
        if not os.path.exists(path):
            print(f"[!] Sin datos de {TIMEFRAME} para {symbol}, se salta")
            continue

        df = load(symbol)
        actual_days = (df["datetime"].max() - df["datetime"].min()).total_seconds() / 86400

        setups = generate_setups(symbol, df)
        results = simulate_trades(setups, df, config.INITIAL_CAPITAL_USDT)
        metrics = compute_metrics(results, config.INITIAL_CAPITAL_USDT)
        metrics["symbol"] = symbol
        metrics["display_name"] = DISPLAY_NAME.get(symbol, symbol)
        metrics["trades_per_day"] = metrics["num_trades"] / actual_days if actual_days > 0 else 0
        metrics["days_analizados"] = round(actual_days, 1)
        rows.append(metrics)

        print(f"{DISPLAY_NAME.get(symbol, symbol):15s} dias={actual_days:5.1f} "
              f"setups={len(setups):4d} trades={metrics['num_trades']:4d} "
              f"trades/dia={metrics['trades_per_day']:.2f} "
              f"win_rate={metrics['win_rate']:.1f}% PF={metrics['profit_factor']:.2f} "
              f"retorno={metrics['total_return_pct']:.2f}% dd={metrics['max_drawdown_pct']:.2f}%")

    df_out = pd.DataFrame(rows)
    out_path = os.path.join(config.RESULTS_DIR, "v6_orderflow_proxy_summary.csv")
    df_out.to_csv(out_path, index=False)
    print(f"\nGuardado en {out_path}")


if __name__ == "__main__":
    main()
