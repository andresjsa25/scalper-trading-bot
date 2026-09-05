"""
Compara las 3 estrategias del bot (V1 Sniper, V5 Fibonacci, V10
Bollinger+RSI) sobre NASDAQ100, GOOGL, META, NVDA -- 8 meses de datos
(15m/1h con ~100 días reales de profundidad en 15m por el límite de
retención de BingX ya documentado; 1h/4h con los 8 meses completos).

Config usada por estrategia:
  - V1: la misma que ya está probada y en vivo para AAPL/NASDAQ100
    (V1_LIVE_CONFIG) -- percentil 0, sin filtro de tendencia, con filtro
    de sesión, EMA10 solo, TP:SL 1:2.3.
  - V5: defaults del propio módulo (percentil 0, sin R:R mínimo exigido)
    -- no hay ninguna config de V5 ya probada en vivo para heredar (V5
    está vacía en producción, ver V5_LIVE_CONFIG en run_live_trading.py),
    así que se usa la config "de fábrica", sin ajustar para la ocasión.
  - V10: defaults del propio módulo (stop_mode="atr", atr_mult=1.5,
    require_pattern=False, rr_ratio=2.0) -- la config ya calibrada de
    V10_LIVE_CONFIG es específica de 6 criptos nativas, no aplica a estos
    4 activos nuevos.

Ningún resultado de V5/V10 acá está calibrado para estos activos --
son un punto de partida "de fábrica" para saber si vale la pena calibrar
más, no un resultado final.
"""
import os
import sys

import pandas as pd

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
import config
from strategy_v1_sniper import generate_setups as gen_v1
from entry_filters import apply_entry_filter
from backtest import simulate_trades as sim_v1, compute_metrics as metrics_v1
from strategy_v5_fib_pullback import generate_setups as gen_v5
from backtest_v5 import simulate_fib_pullback_trades as sim_v5, compute_metrics as metrics_v5
from strategy_v10_bb_rsi_refined import generate_setups as gen_v10
from backtest import simulate_trades as sim_v10, compute_metrics as metrics_v10

SYMBOLS = {
    "NCSINASDAQ1002USD/USDT:USDT": "NASDAQ100",
    "NCSKGOOGL2USD/USDT:USDT": "GOOGL",
    "NCSKMETA2USD/USDT:USDT": "META",
    "NCSKNVDA2USD/USDT:USDT": "NVDA",
}

V1_CFG = {"percentile": 0, "use_trend_filter": False, "use_session_filter": True,
          "require_regime": None, "tp_rr_ratio": 2.3, "ema_filter": "ema_only"}


def load_tf(symbol, tf):
    fname = symbol.replace("/", "_").replace(":", "_")
    df = pd.read_csv(os.path.join(config.DATA_DIR, f"{fname}_{tf}.csv"))
    df["datetime"] = pd.to_datetime(df["datetime"], utc=True)
    return df


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


def row_from(display, strategy, results, metrics, days_span):
    losing_streak, winning_streak = streaks(results)
    return {
        "activo": display, "estrategia": strategy,
        "dias_reales": round(days_span, 1),
        "trades": metrics["num_trades"],
        "trades_por_dia": round(metrics["num_trades"] / days_span, 3) if days_span else 0,
        "win_rate_%": round(metrics["win_rate"], 1) if metrics["num_trades"] else None,
        "profit_factor": round(metrics["profit_factor"], 2) if metrics["num_trades"] else None,
        "roi_%": round(metrics["total_return_pct"], 2),
        "max_drawdown_%": round(metrics["max_drawdown_pct"], 2),
        "racha_perdidas_max": losing_streak,
        "racha_ganancias_max": winning_streak,
        "comisiones_usdt": round(metrics.get("total_fees", 0), 2),
    }


def main():
    os.makedirs(config.RESULTS_DIR, exist_ok=True)
    rows = []

    for symbol, display in SYMBOLS.items():
        df_15m = load_tf(symbol, "15m")
        df_1h = load_tf(symbol, "1h")
        df_4h = load_tf(symbol, "4h")

        # --- V1: entrada 15m, contexto 1h ---
        days_v1 = (df_15m["datetime"].iloc[-1] - df_15m["datetime"].iloc[0]).total_seconds() / 86400
        config.TP_RR_RATIO = V1_CFG["tp_rr_ratio"]
        setups = gen_v1(symbol, df_1h.copy(), df_15m.copy(),
                         min_swing_percentile=V1_CFG["percentile"],
                         use_trend_filter=V1_CFG["use_trend_filter"],
                         use_session_filter=V1_CFG["use_session_filter"],
                         require_regime=V1_CFG["require_regime"])
        setups = apply_entry_filter(setups, df_15m, V1_CFG["ema_filter"])
        results = sim_v1(setups, df_15m, config.INITIAL_CAPITAL_USDT)
        m = metrics_v1(results, config.INITIAL_CAPITAL_USDT)
        rows.append(row_from(display, "V1_sniper", results, m, days_v1))

        # --- V5: entrada 1h, contexto 4h ---
        days_v5 = (df_1h["datetime"].iloc[-1] - df_1h["datetime"].iloc[0]).total_seconds() / 86400
        setups = gen_v5(symbol, df_4h.copy(), df_1h.copy(), min_swing_percentile=0, min_rr_ratio=0)
        results = sim_v5(setups, df_1h, config.INITIAL_CAPITAL_USDT)
        m = metrics_v5(results, config.INITIAL_CAPITAL_USDT)
        rows.append(row_from(display, "V5_fibonacci", results, m, days_v5))

        # --- V10: entrada 1h, contexto 4h ---
        days_v10 = days_v5
        setups = gen_v10(symbol, df_4h.copy(), df_1h.copy(),
                          stop_mode="atr", atr_mult=1.5, require_pattern=False, rr_ratio=2.0)
        results = sim_v10(setups, df_1h, config.INITIAL_CAPITAL_USDT)
        m = metrics_v10(results, config.INITIAL_CAPITAL_USDT)
        rows.append(row_from(display, "V10_bb_rsi", results, m, days_v10))

    df = pd.DataFrame(rows)
    out_path = os.path.join(config.RESULTS_DIR, "backtest_3strategies_comparison.csv")
    df.to_csv(out_path, index=False)

    print(df.to_string(index=False))
    print(f"\nGuardado en {out_path}")

    print("\n=== Mejor estrategia por activo (según profit factor) ===")
    for display in SYMBOLS.values():
        sub = df[df["activo"] == display].dropna(subset=["profit_factor"])
        if sub.empty:
            print(f"  {display}: ninguna estrategia generó trades")
            continue
        best = sub.loc[sub["profit_factor"].idxmax()]
        print(f"  {display}: {best['estrategia']} (PF={best['profit_factor']}, "
              f"ROI={best['roi_%']}%, trades={best['trades']})")


if __name__ == "__main__":
    main()
