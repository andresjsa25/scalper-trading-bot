"""
Backtestea el filtro "esperar 3 velas de 5min tras la señal, entrar a
mercado" en los 6 activos de V1, comparado contra la entrada actual
(límite, inmediata en cuanto toca la zona). Los datos de 5min en BingX
solo tienen ~89 días de historia real -- así que la comparación se hace
en esa MISMA ventana para los dos esquemas (no todo el histórico de 1.5
años que se usa en otros lados), para que sea una comparación justa.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
import config
from strategy_v1_sniper import generate_setups
from backtest import TradeSetup, simulate_trades, compute_metrics

WAIT_BARS_5M = 3

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
    df_5m = pd.read_csv(os.path.join(config.DATA_DIR, f"{fname}_5m.csv"))
    for df in (df_entry, df_context, df_5m):
        df["datetime"] = pd.to_datetime(df["datetime"], utc=True)
    return df_entry, df_context, df_5m


def find_delayed_entry(df_5m, entry_price_target, search_start, search_end, wait_bars=WAIT_BARS_5M):
    window = df_5m[(df_5m["datetime"] >= search_start) & (df_5m["datetime"] <= search_end)].reset_index(drop=True)
    touch_idx = None
    for i, row in window.iterrows():
        if row["low"] <= entry_price_target <= row["high"]:
            touch_idx = i
            break
    if touch_idx is None:
        return None
    delayed_idx = touch_idx + wait_bars
    if delayed_idx >= len(window):
        return None
    bar = window.iloc[delayed_idx]
    return bar["open"], bar["datetime"]


def build_delayed_setups(symbol, original_setups, df_5m):
    delayed = []
    for s in original_setups:
        search_start = s.signal_datetime - pd.Timedelta(minutes=20)
        search_end = s.signal_datetime + pd.Timedelta(hours=2)
        result = find_delayed_entry(df_5m, s.entry_price_target, search_start, search_end)
        if result is None:
            continue
        new_entry_price, new_dt = result
        risk = abs(new_entry_price - s.stop_price)
        if risk <= 0:
            continue
        # dirección ya validada por el sign de risk/estructura original
        delayed.append((s, TradeSetup(
            symbol=symbol, strategy="v1_sniper_delayed3x5m", direction=s.direction,
            signal_bar_pos=s.signal_bar_pos, signal_datetime=new_dt,
            entry_price_target=new_entry_price, stop_price=s.stop_price,
            take_profit_price=s.take_profit_price, valid_until_pos=s.valid_until_pos,
            risk_pct=s.risk_pct, is_limit=False,
        )))
    return delayed


def main():
    os.makedirs(config.RESULTS_DIR, exist_ok=True)
    rows = []
    for symbol, cfg in V1_CONFIGS.items():
        name = DISPLAY_NAME[symbol]
        df_entry, df_context, df_5m = load(symbol)
        config.TP_RR_RATIO = 2.0

        original_setups = generate_setups(
            symbol, df_context, df_entry, min_swing_percentile=cfg["percentile"],
            use_trend_filter=cfg["use_trend_filter"], use_session_filter=cfg["use_session_filter"],
            require_regime=cfg["require_regime"],
        )

        min_5m_dt = df_5m["datetime"].min()
        max_5m_dt = df_5m["datetime"].max()
        window_setups = [s for s in original_setups if min_5m_dt <= s.signal_datetime <= max_5m_dt]
        span_days = (max_5m_dt - min_5m_dt).days or 1

        # Esquema ACTUAL, restringido a la misma ventana de ~89 días (comparación justa)
        results_baseline = simulate_trades(window_setups, df_entry, config.INITIAL_CAPITAL_USDT)
        m_base = compute_metrics(results_baseline, config.INITIAL_CAPITAL_USDT)

        # Esquema DEMORADO (3 velas de 5min, a mercado)
        pairs = build_delayed_setups(symbol, window_setups, df_5m)
        delayed_setups = [d for _, d in pairs]
        results_delayed = simulate_trades(delayed_setups, df_entry, config.INITIAL_CAPITAL_USDT)
        m_delay = compute_metrics(results_delayed, config.INITIAL_CAPITAL_USDT)

        rows.append({
            "symbol": name, "span_days": span_days,
            "base_trades": m_base["num_trades"], "base_tpd": m_base["num_trades"] / span_days,
            "base_win_rate": m_base["win_rate"], "base_pf": m_base["profit_factor"],
            "base_return": m_base["total_return_pct"], "base_dd": m_base["max_drawdown_pct"],
            "delay_trades": m_delay["num_trades"], "delay_tpd": m_delay["num_trades"] / span_days,
            "delay_win_rate": m_delay["win_rate"], "delay_pf": m_delay["profit_factor"],
            "delay_return": m_delay["total_return_pct"], "delay_dd": m_delay["max_drawdown_pct"],
        })
        print(f"{name:15s} ventana={span_days}d | ACTUAL trades={m_base['num_trades']:3d} "
              f"PF={m_base['profit_factor']:.2f} ret={m_base['total_return_pct']:6.2f}% DD={m_base['max_drawdown_pct']:6.2f}% "
              f"|| DEMORADO trades={m_delay['num_trades']:3d} PF={m_delay['profit_factor']:.2f} "
              f"ret={m_delay['total_return_pct']:6.2f}% DD={m_delay['max_drawdown_pct']:6.2f}%")

    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(config.RESULTS_DIR, "v1_delayed_entry_comparison.csv"), index=False)
    print("\nPromedios -- ACTUAL: PF", round(df["base_pf"].mean(), 2), "| DEMORADO: PF", round(df["delay_pf"].mean(), 2))


if __name__ == "__main__":
    main()
