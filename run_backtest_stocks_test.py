"""
Backtest de V1 (Sniper de liquidez) sobre NASDAQ100, GOOGL, META, NVDA con
los datos de 8 meses pedidos (en la práctica: ~3.3 meses de 15min -- límite
real de retención de BingX para estos sintéticos -- y ~8 meses de 1h de
contexto). RUSSELL2000 queda afuera: BingX tiene pausado el histórico de
NCSIRUSSELL20002USD ahora mismo.

Config usada: la MISMA que ya está probada y en vivo para NCSKAAPL2USD /
NCSINASDAQ1002USD en V1_LIVE_CONFIG (percentil 0, sin filtro de tendencia,
con filtro de sesión, EMA10 solo, TP:SL 1:2.3) -- se aplica igual a GOOGL/
META/NVDA por ser el mismo tipo de activo (acción tokenizada de BingX) que
AAPL, no una config inventada para la ocasión. Incluye el mismo
apply_entry_filter que corre run_live_trading.py (el backtest "simple" de
run_backtest_v1.py NO lo aplica -- acá sí, para que el número refleje lo
que de verdad correría en vivo).

Reporta, por símbolo: trades, trades/día, win rate, profit factor, ROI,
max drawdown, R promedio, comisiones totales, y la racha de pérdidas
consecutivas más larga (la métrica que motivó sacar AMZN -- "consistencia"
en la práctica es esto tanto como el profit factor).
"""
import os
import sys

import pandas as pd

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
import config
from strategy_v1_sniper import generate_setups
from entry_filters import apply_entry_filter
from backtest import simulate_trades, compute_metrics

TEST_SYMBOLS = {
    "NCSINASDAQ1002USD/USDT:USDT": "NASDAQ100",
    "NCSKGOOGL2USD/USDT:USDT": "GOOGL",
    "NCSKMETA2USD/USDT:USDT": "META",
    "NCSKNVDA2USD/USDT:USDT": "NVDA",
}

# Config ya probada en vivo para NCSKAAPL2USD / NCSINASDAQ1002USD (V1_LIVE_CONFIG).
LIVE_EQUIVALENT_CFG = {
    "percentile": 0, "use_trend_filter": False, "use_session_filter": True,
    "require_regime": None, "tp_rr_ratio": 2.3, "ema_filter": "ema_only",
}


def load(symbol):
    fname = symbol.replace("/", "_").replace(":", "_")
    df_entry = pd.read_csv(os.path.join(config.DATA_DIR, f"{fname}_{config.TIMEFRAME_ENTRY}.csv"))
    df_context = pd.read_csv(os.path.join(config.DATA_DIR, f"{fname}_{config.TIMEFRAME_CONTEXT}.csv"))
    df_entry["datetime"] = pd.to_datetime(df_entry["datetime"], utc=True)
    df_context["datetime"] = pd.to_datetime(df_context["datetime"], utc=True)
    return df_entry, df_context


def max_consecutive_losses(results):
    streak = worst = 0
    for r in results:
        if r.pnl_net <= 0:
            streak += 1
            worst = max(worst, streak)
        else:
            streak = 0
    return worst


def max_consecutive_wins(results):
    streak = best = 0
    for r in results:
        if r.pnl_net > 0:
            streak += 1
            best = max(best, streak)
        else:
            streak = 0
    return best


def main():
    os.makedirs(config.RESULTS_DIR, exist_ok=True)
    rows = []

    for symbol, display in TEST_SYMBOLS.items():
        fname = symbol.replace("/", "_").replace(":", "_")
        path_entry = os.path.join(config.DATA_DIR, f"{fname}_{config.TIMEFRAME_ENTRY}.csv")
        if not os.path.exists(path_entry):
            print(f"[!] Sin datos para {display}, se salta")
            continue

        df_entry, df_context = load(symbol)
        days_span = (df_entry["datetime"].iloc[-1] - df_entry["datetime"].iloc[0]).total_seconds() / 86400

        config.TP_RR_RATIO = LIVE_EQUIVALENT_CFG["tp_rr_ratio"]
        setups = generate_setups(
            symbol, df_context, df_entry,
            min_swing_percentile=LIVE_EQUIVALENT_CFG["percentile"],
            use_trend_filter=LIVE_EQUIVALENT_CFG["use_trend_filter"],
            use_session_filter=LIVE_EQUIVALENT_CFG["use_session_filter"],
            require_regime=LIVE_EQUIVALENT_CFG["require_regime"],
        )
        setups = apply_entry_filter(setups, df_entry, LIVE_EQUIVALENT_CFG["ema_filter"])

        results = simulate_trades(setups, df_entry, config.INITIAL_CAPITAL_USDT)
        metrics = compute_metrics(results, config.INITIAL_CAPITAL_USDT)

        row = {
            "activo": display,
            "rango_15m": f"{df_entry['datetime'].iloc[0].date()} -> {df_entry['datetime'].iloc[-1].date()}",
            "dias_reales": round(days_span, 1),
            "setups_generados": len(setups),
            "trades_ejecutados": metrics["num_trades"],
            "trades_por_dia": round(metrics["num_trades"] / days_span, 3) if days_span > 0 else 0,
            "win_rate_%": round(metrics["win_rate"], 1) if metrics["num_trades"] else None,
            "profit_factor": round(metrics["profit_factor"], 2) if metrics["num_trades"] else None,
            "roi_%": round(metrics["total_return_pct"], 2),
            "max_drawdown_%": round(metrics["max_drawdown_pct"], 2),
            "r_promedio": round(metrics["avg_r_multiple"], 2) if metrics["num_trades"] else None,
            "racha_perdidas_max": max_consecutive_losses(results),
            "racha_ganancias_max": max_consecutive_wins(results),
            "comisiones_totales_usdt": round(metrics.get("total_fees", 0), 2),
            "capital_final_usdt": round(metrics["final_capital"], 2),
        }
        rows.append(row)

        print(f"\n=== {display} ({symbol}) ===")
        for k, v in row.items():
            print(f"  {k}: {v}")

    df = pd.DataFrame(rows)
    out_path = os.path.join(config.RESULTS_DIR, "backtest_stocks_test_v1.csv")
    df.to_csv(out_path, index=False)
    print(f"\nGuardado en {out_path}")
    print("\n" + "=" * 100)
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
