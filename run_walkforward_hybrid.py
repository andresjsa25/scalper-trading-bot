"""
Walk-forward de la config HÍBRIDA (2026-08-04): EMA10+T-Theory en los
activos que rindieron mejor con el filtro completo (SILVER, OIL_BRENT,
ADA) y solo EMA10 (sin T-Theory) en el resto (SP500, NASDAQ100, XAUT,
AMZN, LINK, BNB), para no perder tanta frecuencia. Mismo criterio de
run_walkforward_v1_final.py: se recalibra SOLO el percentil con ventana
móvil de 90 días (recalibra cada 30), usando nada más que datos ya
pasados en cada punto -- los filtros booleanos (tendencia/sesión/régimen)
y el modo EMA10/EMA10+T quedan fijos por símbolo, ya decididos mirando
todo el histórico (quedan marcados como supuesto, no recalibrados acá).
"""
import os
import sys
from datetime import timedelta

import pandas as pd

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "src", "indicators"))
import config
from strategy_v1_sniper import generate_setups
from backtest import simulate_trades, compute_metrics
from indicators.trend import add_ema, ema_simple_bias
from indicators.t_theory import detect_base_and_t_window

V1_CONFIGS = {
    "NCCOXAG2USD/USDT:USDT": {"use_trend_filter": False, "use_session_filter": True, "require_regime": None, "filter_mode": "ema_t"},
    "NCSISP5002USD/USDT:USDT": {"use_trend_filter": False, "use_session_filter": True, "require_regime": None, "filter_mode": "ema_only"},
    "NCSINASDAQ1002USD/USDT:USDT": {"use_trend_filter": False, "use_session_filter": True, "require_regime": None, "filter_mode": "ema_only"},
    "NCCO1OILBRENT2USD/USDT:USDT": {"use_trend_filter": False, "use_session_filter": True, "require_regime": None, "filter_mode": "ema_t"},
    "XAUT/USDT:USDT": {"use_trend_filter": True, "use_session_filter": False, "require_regime": None, "filter_mode": "ema_only"},
    "NCSKAMZN2USD/USDT:USDT": {"use_trend_filter": False, "use_session_filter": True, "require_regime": None, "filter_mode": "ema_only"},
    "ADA/USDT:USDT": {"use_trend_filter": False, "use_session_filter": True, "require_regime": None, "filter_mode": "ema_t"},
    "LINK/USDT:USDT": {"use_trend_filter": False, "use_session_filter": True, "require_regime": None, "filter_mode": "ema_only"},
    "BNB/USDT:USDT": {"use_trend_filter": False, "use_session_filter": True, "require_regime": None, "filter_mode": "ema_only"},
}
DISPLAY_NAME = {
    "NCCOXAG2USD/USDT:USDT": "SILVER/USD", "NCSISP5002USD/USDT:USDT": "SP500/USD",
    "NCSINASDAQ1002USD/USDT:USDT": "NASDAQ100/USD", "NCCO1OILBRENT2USD/USDT:USDT": "OIL_BRENT/USD",
    "XAUT/USDT:USDT": "XAUT", "NCSKAMZN2USD/USDT:USDT": "AMZN/USD",
    "ADA/USDT:USDT": "ADA", "LINK/USDT:USDT": "LINK", "BNB/USDT:USDT": "BNB",
}

CALIBRATION_WINDOW_DAYS = 90
RECALIBRATION_DAYS = 30
PERCENTILE_GRID = [0, 20, 30, 40, 50, 60, 70, 80, 90]
MIN_PF = 1.0
config.TP_RR_RATIO = 2.0


def load(symbol):
    fname = symbol.replace("/", "_").replace(":", "_")
    df_entry = pd.read_csv(os.path.join(config.DATA_DIR, f"{fname}_15m.csv"))
    df_context = pd.read_csv(os.path.join(config.DATA_DIR, f"{fname}_1h.csv"))
    df_entry["datetime"] = pd.to_datetime(df_entry["datetime"], utc=True)
    df_context["datetime"] = pd.to_datetime(df_context["datetime"], utc=True)
    return df_entry, df_context


def slice_between(df, start_dt, end_dt):
    return df[(df["datetime"] >= start_dt) & (df["datetime"] < end_dt)].reset_index(drop=True)


def apply_filter(setups, df_entry_slice, filter_mode):
    if not setups:
        return setups
    df_ind = add_ema(df_entry_slice.copy(), 10, "ema10")
    df_ind["ema10_bias"] = ema_simple_bias(df_ind, "ema10")
    if filter_mode == "ema_t":
        df_ind = detect_base_and_t_window(df_ind)

    kept = []
    for s in setups:
        row = df_ind.iloc[s.signal_bar_pos]
        required_bias = "up" if s.direction == "long" else "down"
        if row["ema10_bias"] != required_bias:
            continue
        if filter_mode == "ema_t" and not bool(row["in_t_window"]):
            continue
        kept.append(s)
    return kept


def pick_best_percentile(symbol, train_entry, train_context, cfg):
    candidates = []
    for pct in PERCENTILE_GRID:
        setups = generate_setups(symbol, train_context.copy(), train_entry.copy(), min_swing_percentile=pct,
                                  use_trend_filter=cfg["use_trend_filter"], use_session_filter=cfg["use_session_filter"],
                                  require_regime=cfg["require_regime"])
        setups = apply_filter(setups, train_entry, cfg["filter_mode"])
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
        setups = apply_filter(setups, oos_entry, cfg["filter_mode"])
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
        m.update({"symbol": DISPLAY_NAME[symbol], "filter_mode": cfg["filter_mode"], "oos_days": oos_days,
                  "trades_per_day": m["num_trades"] / oos_days if oos_days else 0})
        summary_rows.append(m)
        print(f"{DISPLAY_NAME[symbol]:15s} [{cfg['filter_mode']:9s}] trades={m['num_trades']:4d} "
              f"win_rate={m['win_rate']:.1f}% PF={m['profit_factor']:.2f} retorno={m['total_return_pct']:.2f}% "
              f"maxDD={m['max_drawdown_pct']:.2f}% tpd={m['trades_per_day']:.3f}")

    df = pd.DataFrame(summary_rows)
    df.to_csv(os.path.join(config.RESULTS_DIR, "v1_hybrid_walkforward_summary.csv"), index=False)
    pd.DataFrame(all_fold_logs).to_csv(os.path.join(config.RESULTS_DIR, "v1_hybrid_walkforward_folds.csv"), index=False)

    total_trades = df["num_trades"].sum()
    total_tpd = df["trades_per_day"].sum()
    print(f"\nTOTAL walk-forward (out-of-sample), 9 activos V1: {total_trades} trades -> {total_tpd:.3f} trades/día")
    print(f"PF promedio: {df['profit_factor'].mean():.2f} | símbolos con PF>=1: {(df['profit_factor'] >= 1).sum()}/{len(df)}")
    print(f"Combinado con V5 (0.528 trades/día, sin cambios): {total_tpd + 0.528:.3f} trades/día")


if __name__ == "__main__":
    main()
