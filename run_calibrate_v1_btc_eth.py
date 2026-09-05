"""
Calibración de V1 para BTC y ETH (los 2 que quedaron negativos/débiles al
migrarlos desde V5). Mismo criterio de selección que
run_calibrate_v1_per_symbol.py (entre los candidatos con PF>=1.0, el que
más trades tenga; si ninguno llega a PF>=1, el de mejor PF) pero con una
grilla más amplia: percentil x filtro EMA x filtro de tendencia -- los
mismos 3 parámetros que varían entre símbolos en V1_LIVE_CONFIG.

No es el mismo proceso completo (walk-forward, sweep de R:R) que se usó
para calibrar los 8 símbolos originales -- eso llevó varios scripts y
días. Esto es un grid search directo sobre el histórico completo, más
simple pero con los mismos 3 parámetros que ya se sabe que importan.
"""
import os
import sys

import pandas as pd

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
import config
from strategy_v1_sniper import generate_setups
from entry_filters import apply_entry_filter
from backtest import simulate_trades, compute_metrics

SYMBOLS = ["BTC/USDT:USDT", "ETH/USDT:USDT"]
PERCENTILE_GRID = [0, 20, 30, 40, 50, 60, 70, 80, 90]
EMA_FILTER_GRID = ["none", "ema_only", "ema_t"]
TREND_FILTER_GRID = [False, True]
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
    all_rows = []
    best_rows = []

    for symbol in SYMBOLS:
        df_entry, df_context = load(symbol)
        span_days = (df_entry["datetime"].max() - df_entry["datetime"].min()).days
        candidates = []

        for pct in PERCENTILE_GRID:
            for trend in TREND_FILTER_GRID:
                base_setups = generate_setups(
                    symbol, df_context, df_entry,
                    min_swing_percentile=pct, use_trend_filter=trend,
                )
                for ema_mode in EMA_FILTER_GRID:
                    setups = apply_entry_filter(base_setups, df_entry, ema_mode)
                    results = simulate_trades(setups, df_entry, config.INITIAL_CAPITAL_USDT)
                    m = compute_metrics(results, config.INITIAL_CAPITAL_USDT)
                    m.update({
                        "symbol": symbol, "min_swing_percentile": pct,
                        "use_trend_filter": trend, "ema_filter": ema_mode,
                        "trades_per_day": m["num_trades"] / span_days if span_days else 0,
                    })
                    all_rows.append(m)
                    candidates.append(m)

        profitable = [c for c in candidates if c["profit_factor"] >= MIN_PF and c["num_trades"] >= 10]
        pool = profitable if profitable else candidates
        best = max(pool, key=lambda c: (c["num_trades"] if profitable else c["profit_factor"]))
        best_rows.append(best)

        print(f"{symbol:15s} mejor: percentil={best['min_swing_percentile']:3d} "
              f"trend_filter={best['use_trend_filter']} ema_filter={best['ema_filter']:10s} "
              f"trades={best['num_trades']:4d} ({best['trades_per_day']:.3f}/día) "
              f"win_rate={best['win_rate']:.1f}% PF={best['profit_factor']:.2f} "
              f"retorno={best['total_return_pct']:.2f}% dd={best['max_drawdown_pct']:.2f}%")

    pd.DataFrame(all_rows).to_csv(os.path.join(config.RESULTS_DIR, "v1_btc_eth_calibration_all.csv"), index=False)
    pd.DataFrame(best_rows).to_csv(os.path.join(config.RESULTS_DIR, "v1_btc_eth_calibration_best.csv"), index=False)
    print("\nGuardado en results/v1_btc_eth_calibration_best.csv (y _all.csv con la grilla completa)")


if __name__ == "__main__":
    main()
