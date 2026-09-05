"""
Walk-forward de V1 (ganador claro de las 3 estrategias, ver
backtest_3strategies_comparison.csv) sobre NASDAQ100, GOOGL, META, NVDA --
mismo método que run_walkforward_v1.py (recalibrar el percentil SOLO con
datos pasados, operar el tramo siguiente que la calibración nunca vio), en
un script separado para no tocar ese archivo ya validado con los otros
8 activos.

Diferencia a propósito frente a run_walkforward_v1.py: acá se aplica
también el filtro EMA10 (ema_only) y TP:SL 1:2.3 en cada tramo
out-of-sample, para validar la MISMA configuración que ganó en la
comparación estática (ahí sí tenía el filtro EMA aplicado) -- si se
dejaba como el original (sin EMA, TP:SL 1:2.0) no se estaría probando lo
mismo que dio esos resultados.

Ventanas MÁS CHICAS que el run_walkforward_v1.py original (45 días de
calibración / 15 de recalibración, en vez de 90/30): estos 4 activos solo
tienen ~100 días reales de 15min (límite de retención de BingX, ya
documentado). Con las ventanas originales (90/30) quedarían ~10 días
out-of-sample en total -- inútil para sacar ninguna conclusión. Con 45/15
se logran ~3-4 tramos out-of-sample (~45-55 días combinados) -- sigue
siendo poco al lado de los activos con 1.5 años de historia, pero es lo
más que se puede exprimir con la profundidad de datos que hay hoy. Esto
se vuelve a correr con ventanas normales el día que BingX permita bajar
más historia de 15min para estos símbolos (o si se decide operarlos en un
timeframe con más profundidad disponible).
"""
import os
import sys
from datetime import timedelta

import pandas as pd

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
import config
from strategy_v1_sniper import generate_setups
from entry_filters import apply_entry_filter
from backtest import simulate_trades, compute_metrics

SYMBOLS = {
    "NCSINASDAQ1002USD/USDT:USDT": "NASDAQ100",
    "NCSKGOOGL2USD/USDT:USDT": "GOOGL",
    "NCSKMETA2USD/USDT:USDT": "META",
    "NCSKNVDA2USD/USDT:USDT": "NVDA",
}

CALIBRATION_WINDOW_DAYS = 45   # reducido de 90 (ver docstring -- poca profundidad de 15m disponible)
RECALIBRATION_DAYS = 15        # reducido de 30
PERCENTILE_GRID = [0, 20, 30, 40, 50, 60, 70, 80, 90]
MIN_PF = 1.0
EMA_FILTER = "ema_only"
config.TP_RR_RATIO = 2.3


def load(symbol):
    fname = symbol.replace("/", "_").replace(":", "_")
    df_entry = pd.read_csv(os.path.join(config.DATA_DIR, f"{fname}_{config.TIMEFRAME_ENTRY}.csv"))
    df_context = pd.read_csv(os.path.join(config.DATA_DIR, f"{fname}_{config.TIMEFRAME_CONTEXT}.csv"))
    df_entry["datetime"] = pd.to_datetime(df_entry["datetime"], utc=True)
    df_context["datetime"] = pd.to_datetime(df_context["datetime"], utc=True)
    return df_entry, df_context


def slice_between(df, start_dt, end_dt):
    return df[(df["datetime"] >= start_dt) & (df["datetime"] < end_dt)].reset_index(drop=True)


def pick_best_percentile(symbol, train_entry, train_context):
    candidates = []
    for pct in PERCENTILE_GRID:
        setups = generate_setups(symbol, train_context.copy(), train_entry.copy(), min_swing_percentile=pct)
        setups = apply_entry_filter(setups, train_entry, EMA_FILTER)
        results = simulate_trades(setups, train_entry, config.INITIAL_CAPITAL_USDT)
        m = compute_metrics(results, config.INITIAL_CAPITAL_USDT)
        candidates.append((pct, m))
    profitable = [c for c in candidates if c[1]["profit_factor"] >= MIN_PF]
    pool = profitable if profitable else candidates
    best = max(pool, key=lambda c: c[1]["num_trades"] if profitable else c[1]["profit_factor"])
    return best[0]


def streaks(results):
    worst = best = streak_l = streak_w = 0
    for r in results:
        if r.pnl_net <= 0:
            streak_l += 1
            streak_w = 0
            worst = max(worst, streak_l)
        else:
            streak_w += 1
            streak_l = 0
            best = max(best, streak_w)
    return worst, best


def walkforward_symbol(symbol):
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
        best_pct = pick_best_percentile(symbol, train_entry, train_context)

        oos_end = min(t + timedelta(days=RECALIBRATION_DAYS), end)
        oos_entry = slice_between(df_entry, train_start, oos_end)
        oos_context = slice_between(df_context, train_start, oos_end)
        setups = generate_setups(symbol, oos_context.copy(), oos_entry.copy(), min_swing_percentile=best_pct)
        setups = apply_entry_filter(setups, oos_entry, EMA_FILTER)
        oos_setups = [s for s in setups if s.signal_datetime >= t]

        results = simulate_trades(oos_setups, oos_entry, capital)
        if results:
            capital = results[-1].capital_after
        all_results.extend(results)
        fold_log.append({"symbol": SYMBOLS[symbol], "fold_start": t.date(), "fold_end": oos_end.date(),
                          "chosen_percentile": best_pct, "n_trades": len(results)})
        t = oos_end

    return all_results, fold_log


def main():
    os.makedirs(config.RESULTS_DIR, exist_ok=True)
    summary_rows = []
    all_fold_logs = []

    only = sys.argv[1] if len(sys.argv) > 1 else None
    items = SYMBOLS.items() if not only else [(s, d) for s, d in SYMBOLS.items() if d == only]

    for symbol, display in items:
        results, fold_log = walkforward_symbol(symbol)
        all_fold_logs.extend(fold_log)
        m = compute_metrics(results, config.INITIAL_CAPITAL_USDT)
        df_entry, _ = load(symbol)
        oos_days = (df_entry["datetime"].max() - (df_entry["datetime"].min() + timedelta(days=CALIBRATION_WINDOW_DAYS))).total_seconds() / 86400
        losing_streak, winning_streak = streaks(results)
        m.update({"symbol": display, "oos_days": round(oos_days, 1),
                  "trades_per_day": m["num_trades"] / oos_days if oos_days > 0 else 0,
                  "n_folds": len(fold_log),
                  "racha_perdidas_max": losing_streak, "racha_ganancias_max": winning_streak})
        summary_rows.append(m)
        pf_str = f"{m['profit_factor']:.2f}" if m["num_trades"] else "n/a"
        print(f"{display:12s} folds={len(fold_log)} oos_days={oos_days:5.1f} trades={m['num_trades']:4d} "
              f"win_rate={m['win_rate']:.1f}% PF={pf_str} retorno={m['total_return_pct']:.2f}% "
              f"maxDD={m['max_drawdown_pct']:.2f}%")

    suffix = f"_{only}" if only else ""
    df = pd.DataFrame(summary_rows)
    df.to_csv(os.path.join(config.RESULTS_DIR, f"stocks_test_walkforward_summary{suffix}.csv"), index=False)
    fold_df = pd.DataFrame(all_fold_logs)
    fold_df.to_csv(os.path.join(config.RESULTS_DIR, f"stocks_test_walkforward_folds{suffix}.csv"), index=False)

    print("\n=== Detalle de tramos (qué percentil se eligió cada vez) ===")
    print(fold_df.to_string(index=False))


if __name__ == "__main__":
    main()
