"""
Prueba sacar el filtro T-Theory y dejar solo EMA10 (nunca operar en contra),
en los 9 activos V1 (los 6 originales + ADA/LINK/BNB, agregados 2026-08-04),
para ver si recupera trades/día sin perder demasiado PF -- opción 1 sugerida
al usuario para acercarse a 2 trades/día combinados.
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
    "ADA/USDT:USDT": {"percentile": 0, "use_trend_filter": False, "use_session_filter": True, "require_regime": None},
    "LINK/USDT:USDT": {"percentile": 0, "use_trend_filter": False, "use_session_filter": True, "require_regime": None},
    "BNB/USDT:USDT": {"percentile": 0, "use_trend_filter": False, "use_session_filter": True, "require_regime": None},
}
DISPLAY_NAME = {
    "NCCOXAG2USD/USDT:USDT": "SILVER/USD", "NCSISP5002USD/USDT:USDT": "SP500/USD",
    "NCSINASDAQ1002USD/USDT:USDT": "NASDAQ100/USD", "NCCO1OILBRENT2USD/USDT:USDT": "OIL_BRENT/USD",
    "XAUT/USDT:USDT": "XAUT", "NCSKAMZN2USD/USDT:USDT": "AMZN/USD",
    "ADA/USDT:USDT": "ADA", "LINK/USDT:USDT": "LINK", "BNB/USDT:USDT": "BNB",
}


def load(symbol):
    fname = symbol.replace("/", "_").replace(":", "_")
    df_entry = pd.read_csv(os.path.join(config.DATA_DIR, f"{fname}_15m.csv"))
    df_context = pd.read_csv(os.path.join(config.DATA_DIR, f"{fname}_1h.csv"))
    df_entry["datetime"] = pd.to_datetime(df_entry["datetime"], utc=True)
    df_context["datetime"] = pd.to_datetime(df_context["datetime"], utc=True)
    return df_entry, df_context


def apply_ema10_only(setups, df_entry_indexed):
    kept = []
    for s in setups:
        required_bias = "up" if s.direction == "long" else "down"
        if df_entry_indexed["ema10_bias"].iloc[s.signal_bar_pos] != required_bias:
            continue
        kept.append(s)
    return kept


def apply_ema10_ttheory(setups, df_entry_indexed):
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

        ema_only_setups = apply_ema10_only(baseline_setups, df_entry_ind)
        ema_t_setups = apply_ema10_ttheory(baseline_setups, df_entry_ind)

        span_days = (df_entry["datetime"].max() - df_entry["datetime"].min()).days or 1

        m_base = compute_metrics(simulate_trades(baseline_setups, df_entry, config.INITIAL_CAPITAL_USDT), config.INITIAL_CAPITAL_USDT)
        m_ema = compute_metrics(simulate_trades(ema_only_setups, df_entry, config.INITIAL_CAPITAL_USDT), config.INITIAL_CAPITAL_USDT)
        m_emat = compute_metrics(simulate_trades(ema_t_setups, df_entry, config.INITIAL_CAPITAL_USDT), config.INITIAL_CAPITAL_USDT)

        rows.append({
            "symbol": name, "span_days": span_days,
            "base_trades": m_base["num_trades"], "base_tpd": m_base["num_trades"] / span_days, "base_pf": m_base["profit_factor"],
            "ema_trades": m_ema["num_trades"], "ema_tpd": m_ema["num_trades"] / span_days, "ema_pf": m_ema["profit_factor"],
            "ema_return": m_ema["total_return_pct"], "ema_dd": m_ema["max_drawdown_pct"],
            "emat_trades": m_emat["num_trades"], "emat_tpd": m_emat["num_trades"] / span_days, "emat_pf": m_emat["profit_factor"],
        })
        print(f"{name:12s} | BASE trades={m_base['num_trades']:3d} PF={m_base['profit_factor']:.2f} "
              f"|| SOLO EMA10 trades={m_ema['num_trades']:3d} tpd={m_ema['num_trades']/span_days:.3f} "
              f"PF={m_ema['profit_factor']:.2f} ret={m_ema['total_return_pct']:6.2f}% DD={m_ema['max_drawdown_pct']:6.2f}% "
              f"|| EMA10+T trades={m_emat['num_trades']:3d} tpd={m_emat['num_trades']/span_days:.3f} PF={m_emat['profit_factor']:.2f}")

    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(config.RESULTS_DIR, "v1_ema_only_vs_ema_ttheory_9assets.csv"), index=False)
    print(f"\nTotal trades/día -- BASE: {df['base_tpd'].sum():.3f} | SOLO EMA10: {df['ema_tpd'].sum():.3f} "
          f"| EMA10+T: {df['emat_tpd'].sum():.3f}")
    print(f"PF promedio -- BASE: {df['base_pf'].mean():.2f} | SOLO EMA10: {df['ema_pf'].mean():.2f} "
          f"| EMA10+T: {df['emat_pf'].mean():.2f}")


if __name__ == "__main__":
    main()
