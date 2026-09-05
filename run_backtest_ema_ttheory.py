"""
Backtestea agregar dos reglas a los 6 activos de V1 (config ya calibrada,
misma que usa run_backtest_delayed_entry.py):
  1. EMA10 (temporalidad de entrada, 15m): nunca operar en contra --
     long solo si close > ema10 en la vela de señal, short solo si close < ema10.
  2. Indicador T de Terry Laundry (versión de simetría temporal sobre
     precio, src/indicators/t_theory.py): solo operar si la vela de señal
     sigue DENTRO de la ventana T proyectada de la última base detectada.

Put/Call ratio queda deliberadamente FUERA (sin fuente de datos históricos
gratuita que cubra la ventana del backtest -- decisión del usuario 2026-08-04).

No se toca strategy_v1_sniper.py (usado por el bot en vivo): las señales
se generan igual que siempre y este script solo las FILTRA después.
"""
import os
import sys

import pandas as pd

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "src", "indicators"))
import config
from strategy_v1_sniper import generate_setups
from backtest import simulate_trades, compute_metrics
from indicators.trend import add_ema, ema_simple_bias
from indicators.t_theory import detect_base_and_t_window

V1_CONFIGS = {
    "NCCOXAG2USD/USDT:USDT": {"percentile": 0, "use_trend_filter": False, "use_session_filter": True, "require_regime": None},
    "NCSISP5002USD/USDT:USDT": {"percentile": 20, "use_trend_filter": False, "use_session_filter": True, "require_regime": None},
    "NCSINASDAQ1002USD/USDT:USDT": {"percentile": 0, "use_trend_filter": False, "use_session_filter": True, "require_regime": None},
    "NCCO1OILBRENT2USD/USDT:USDT": {"percentile": 0, "use_trend_filter": False, "use_session_filter": True, "require_regime": None},
    "XAUT/USDT:USDT": {"percentile": 0, "use_trend_filter": True, "use_session_filter": False, "require_regime": None},
    "NCSKAMZN2USD/USDT:USDT": {"percentile": 0, "use_trend_filter": False, "use_session_filter": True, "require_regime": None},
}
DISPLAY_NAME = {
    "NCCOXAG2USD/USDT:USDT": "SILVER/USD", "NCSISP5002USD/USDT:USDT": "SP500/USD",
    "NCSINASDAQ1002USD/USDT:USDT": "NASDAQ100/USD", "NCCO1OILBRENT2USD/USDT:USDT": "OIL_BRENT/USD",
    "XAUT/USDT:USDT": "XAUT", "NCSKAMZN2USD/USDT:USDT": "AMZN/USD",
}


def load(symbol):
    fname = symbol.replace("/", "_").replace(":", "_")
    df_entry = pd.read_csv(os.path.join(config.DATA_DIR, f"{fname}_15m.csv"))
    df_context = pd.read_csv(os.path.join(config.DATA_DIR, f"{fname}_1h.csv"))
    df_entry["datetime"] = pd.to_datetime(df_entry["datetime"], utc=True)
    df_context["datetime"] = pd.to_datetime(df_context["datetime"], utc=True)
    return df_entry, df_context


def apply_ema10_ttheory_filter(setups, df_entry_indexed):
    kept = []
    for s in setups:
        row = df_entry_indexed.iloc[s.signal_bar_pos]
        required_bias = "up" if s.direction == "long" else "down"
        if row["ema10_bias"] != required_bias:
            continue
        if not bool(row["in_t_window"]):
            continue
        kept.append(s)
    return kept


def main():
    os.makedirs(config.RESULTS_DIR, exist_ok=True)
    rows = []
    for symbol, cfg in V1_CONFIGS.items():
        name = DISPLAY_NAME[symbol]
        df_entry, df_context = load(symbol)
        config.TP_RR_RATIO = 2.0

        baseline_setups = generate_setups(
            symbol, df_context.copy(), df_entry.copy(), min_swing_percentile=cfg["percentile"],
            use_trend_filter=cfg["use_trend_filter"], use_session_filter=cfg["use_session_filter"],
            require_regime=cfg["require_regime"],
        )

        df_entry_ind = add_ema(df_entry.copy(), 10, "ema10")
        df_entry_ind["ema10_bias"] = ema_simple_bias(df_entry_ind, "ema10")
        df_entry_ind = detect_base_and_t_window(df_entry_ind)

        filtered_setups = apply_ema10_ttheory_filter(baseline_setups, df_entry_ind)

        span_days = (df_entry["datetime"].max() - df_entry["datetime"].min()).days or 1

        results_base = simulate_trades(baseline_setups, df_entry, config.INITIAL_CAPITAL_USDT)
        m_base = compute_metrics(results_base, config.INITIAL_CAPITAL_USDT)

        results_filt = simulate_trades(filtered_setups, df_entry, config.INITIAL_CAPITAL_USDT)
        m_filt = compute_metrics(results_filt, config.INITIAL_CAPITAL_USDT)

        rows.append({
            "symbol": name, "span_days": span_days,
            "base_trades": m_base["num_trades"], "base_tpd": m_base["num_trades"] / span_days,
            "base_win_rate": m_base["win_rate"], "base_pf": m_base["profit_factor"],
            "base_return": m_base["total_return_pct"], "base_dd": m_base["max_drawdown_pct"],
            "new_trades": m_filt["num_trades"], "new_tpd": m_filt["num_trades"] / span_days,
            "new_win_rate": m_filt["win_rate"], "new_pf": m_filt["profit_factor"],
            "new_return": m_filt["total_return_pct"], "new_dd": m_filt["max_drawdown_pct"],
        })
        print(f"{name:15s} ventana={span_days}d | BASE trades={m_base['num_trades']:3d} "
              f"PF={m_base['profit_factor']:.2f} ret={m_base['total_return_pct']:6.2f}% DD={m_base['max_drawdown_pct']:6.2f}% "
              f"|| EMA10+T trades={m_filt['num_trades']:3d} PF={m_filt['profit_factor']:.2f} "
              f"ret={m_filt['total_return_pct']:6.2f}% DD={m_filt['max_drawdown_pct']:6.2f}%")

    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(config.RESULTS_DIR, "v1_ema10_ttheory_comparison.csv"), index=False)
    print("\nPromedios -- BASE: PF", round(df["base_pf"].mean(), 2), "| EMA10+T: PF", round(df["new_pf"].mean(), 2))


if __name__ == "__main__":
    main()
