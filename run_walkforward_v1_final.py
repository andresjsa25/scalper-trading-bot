"""
Walk-forward de la config FINAL de V1 (6 activos: SILVER, SP500, NASDAQ100,
OIL_BRENT, XAUT, AMZN). Se mantienen fijos los filtros booleanos ya
decididos por símbolo (tendencia/sesión/régimen -- esos también se
eligieron mirando todo el histórico, así que quedan marcados como
supuesto, no recalibrados acá) y se recalibra SOLO el percentil,
usando nada más que datos ya pasados en cada punto (ventana móvil de 90
días, recalibra cada 30 días) -- igual criterio que
fibo-reversal-bot/src/indicators/fractals.py.
"""
import os
import sys
from datetime import timedelta

import pandas as pd

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
import config
from strategy_v1_sniper import generate_setups
from backtest import simulate_trades, compute_metrics

V1_CONFIGS = {
    "NCCOXAG2USD/USDT:USDT": {"use_trend_filter": False, "use_session_filter": True, "require_regime": None},
    "NCSISP5002USD/USDT:USDT": {"use_trend_filter": False, "use_session_filter": True, "require_regime": None},
    "NCSINASDAQ1002USD/USDT:USDT": {"use_trend_filter": False, "use_session_filter": True, "require_regime": None},
    "NCCO1OILBRENT2USD/USDT:USDT": {"use_trend_filter": False, "use_session_filter": True, "require_regime": None},
    "XAUT/USDT:USDT": {"use_trend_filter": True, "use_session_filter": False, "require_regime": None},
    "NCSKAMZN2USD/USDT:USDT": {"use_trend_filter": False, "use_session_filter": True, "require_regime": None},
}
DISPLAY_NAME = {
    "NCCOXAG2USD/USDT:USDT": "SILVER/USD", "NCSISP5002USD/USDT:USDT": "SP500/USD",
    "NCSINASDAQ1002USD/USDT:USDT": "NASDAQ100/USD", "NCCO1OILBRENT2USD/USDT:USDT": "OIL_BRENT/USD",
    "XAUT/USDT:USDT": "XAUT", "NCSKAMZN2USD/USDT:USDT": "AMZN/USD",
}

CALIBRATION_WINDOW_DAYS = 90
RECALIBRATION_DAYS = 30
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


def slice_between(df, start_dt, end_dt):
    return df[(df["datetime"] >= start_dt) & (df["datetime"] < end_dt)].reset_index(drop=True)


def pick_best_percentile(symbol, train_entry, train_context, cfg):
    candidates = []
    for pct in PERCENTILE_GRID:
        setups = generate_setups(symbol, train_context.copy(), train_entry.copy(), min_swing_percentile=pct,
                                  use_trend_filter=cfg["use_trend_filter"], use_session_filter=cfg["use_session_filter"],
                                  require_regime=cfg["require_regime"])
        results = simulate_trades(setups, train_entry, config.INITIAL_CAPITAL_USDT)
        m = compute_metrics(results, config.INITIAL_CAPITAL_USDT)
        candidates.append((pct, m))
    profitable = [c for c in candidates if c[1]["profit_factor"] >= MIN_PF]
    pool = profitable if profitable else candidates
    best = max(pool, key=lambda c: c[1]["num_trades"] if profitable else c[1]["profit_factor"])
    return best[0]


def walkforward_symbol(symbol, cfg):
    df_entry, df_context = load(symbol)
    start = df_entry["datetime"].min()
    end = df_entry["datetime"].max()
    first_recalib = start + timedelta(days=CALIBRATION_WINDOW_DAYS)
    if first_recalib >= end:
        return [], []

    capital = config.INITIAL_CAPITAL_USDT
    all_results = []
    fold_log = []
    t = first_recalib

    while t < end:
        train_start = t - timedelta(days=CALIBRATION_WINDOW_DAYS)
        train_entry = slice_between(df_entry, train_start, t)
        train_context = slice_between(df_context, train_start, t)
        best_pct = pick_best_percentile(symbol, train_entry, train_context, cfg)

        oos_end = min(t + timedelta(days=RECALIBRATION_DAYS), end)
        oos_entry = slice_between(df_entry, train_start, oos_end)
        oos_context = slice_between(df_context, train_start, oos_end)
        setups = generate_setups(symbol, oos_context.copy(), oos_entry.copy(), min_swing_percentile=best_pct,
                                  use_trend_filter=cfg["use_trend_filter"], use_session_filter=cfg["use_session_filter"],
                                  require_regime=cfg["require_regime"])
        oos_setups = [s for s in setups if s.signal_datetime >= t]

        results = simulate_trades(oos_setups, oos_entry, capital)
        if results:
            capital = results[-1].capital_after
        all_results.extend(results)
        fold_log.append({"symbol": DISPLAY_NAME[symbol], "fold_start": t.date(), "chosen_percentile": best_pct,
                          "n_trades": len(results)})
        t = oos_end

    return all_results, fold_log


def main():
    os.makedirs(config.RESULTS_DIR, exist_ok=True)
    summary_rows = []
    all_fold_logs = []

    for symbol, cfg in V1_CONFIGS.items():
        results, fold_log = walkforward_symbol(symbol, cfg)
        all_fold_logs.extend(fold_log)
        m = compute_metrics(results, config.INITIAL_CAPITAL_USDT)
        df_entry, _ = load(symbol)
        oos_days = (df_entry["datetime"].max() - (df_entry["datetime"].min() + timedelta(days=CALIBRATION_WINDOW_DAYS))).days
        m.update({"symbol": DISPLAY_NAME[symbol], "oos_days": oos_days,
                  "trades_per_day": m["num_trades"] / oos_days if oos_days else 0})
        summary_rows.append(m)
        print(f"{DISPLAY_NAME[symbol]:15s} trades={m['num_trades']:4d} win_rate={m['win_rate']:.1f}% "
              f"PF={m['profit_factor']:.2f} retorno={m['total_return_pct']:.2f}% "
              f"maxDD={m['max_drawdown_pct']:.2f}%")

    df = pd.DataFrame(summary_rows)
    df.to_csv(os.path.join(config.RESULTS_DIR, "v1_final_walkforward_summary.csv"), index=False)
    pd.DataFrame(all_fold_logs).to_csv(os.path.join(config.RESULTS_DIR, "v1_final_walkforward_folds.csv"), index=False)

    total_trades = df["num_trades"].sum()
    total_tpd = df["trades_per_day"].sum()
    print(f"\nTOTAL walk-forward (out-of-sample): {total_trades} trades -> {total_tpd:.2f} trades/día combinados")
    print(f"PF promedio: {df['profit_factor'].mean():.2f} | símbolos con PF>=1: {(df['profit_factor'] >= 1).sum()}/{len(df)}")


if __name__ == "__main__":
    main()
