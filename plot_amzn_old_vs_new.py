"""
Grafica 3 entradas recientes de AMZN con la versión VIEJA (V1 tal cual está
en vivo hoy, sin EMA10/T-Theory) contra 3 entradas recientes con la versión
NUEVA (V1 + filtro EMA10 -- AMZN quedó asignado a "solo EMA10", no
EMA10+T-Theory, en la config híbrida del 2026-08-04) para verificación
visual antes de decidir si se lleva a vivo. No modifica strategy_v1_sniper.py
ni el bot en vivo -- solo lee y filtra después, igual que
run_backtest_ema_ttheory.py.
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mplfinance as mpf
import pandas as pd

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "src", "indicators"))
import config
from strategy_v1_sniper import generate_setups, prepare
from backtest import simulate_trades
from indicators.trend import add_ema, ema_simple_bias

SYMBOL = "NCSKAMZN2USD/USDT:USDT"
CFG = {"percentile": 0, "use_trend_filter": False, "use_session_filter": True, "require_regime": None, "tp_rr_ratio": 2.0}
BARS_BEFORE = 20
BARS_AFTER = 10
N_EXAMPLES = 3


def load(symbol):
    fname = symbol.replace("/", "_").replace(":", "_")
    df_entry = pd.read_csv(os.path.join(config.DATA_DIR, f"{fname}_15m.csv"))
    df_context = pd.read_csv(os.path.join(config.DATA_DIR, f"{fname}_1h.csv"))
    df_entry["datetime"] = pd.to_datetime(df_entry["datetime"], utc=True)
    df_context["datetime"] = pd.to_datetime(df_context["datetime"], utc=True)
    return df_entry, df_context


def find_fvg_zone(df_entry_enriched, setup):
    top_col = "fvg_bear_top" if setup.direction == "short" else "fvg_bull_top"
    bottom_col = "fvg_bear_bottom" if setup.direction == "short" else "fvg_bull_bottom"
    fvg_col = "fvg_bear" if setup.direction == "short" else "fvg_bull"

    search_start = max(0, setup.signal_bar_pos - 40)
    window = df_entry_enriched.iloc[search_start:setup.signal_bar_pos + 1]
    matches = window[window[fvg_col] & (
        (window[top_col] - setup.entry_price_target).abs() < 1e-6
        if setup.direction == "long" else
        (window[bottom_col] - setup.entry_price_target).abs() < 1e-6
    )]
    if len(matches) == 0:
        return None, None
    row = matches.iloc[-1]
    return row[bottom_col], row[top_col]


def plot_trade(df_entry, df_entry_p, setup, result, idx, tag):
    zone_bottom, zone_top = find_fvg_zone(df_entry_p, setup)

    entry_pos = int(df_entry["datetime"].searchsorted(setup.signal_datetime))
    exit_pos = int(df_entry["datetime"].searchsorted(result.exit_datetime))
    start_pos = max(0, entry_pos - BARS_BEFORE)
    end_pos = min(len(df_entry) - 1, exit_pos + BARS_AFTER)

    window = df_entry.iloc[start_pos:end_pos + 1].copy()
    window = window.set_index(pd.DatetimeIndex(window["datetime"]))
    ohlc = window[["open", "high", "low", "close", "volume"]]

    addplots = []
    if tag == "NUEVA (EMA10)":
        ema_window = df_entry.iloc[max(0, start_pos - 10):end_pos + 1].copy()
        ema_window = add_ema(ema_window, 10, "ema10")
        ema_aligned = ema_window.set_index(pd.DatetimeIndex(ema_window["datetime"])).reindex(window.index)["ema10"]
        addplots.append(mpf.make_addplot(ema_aligned, color="orange", width=1.3))

    plot_kwargs = dict(
        type="candle", style="charles",
        title=f"AMZN {tag} #{idx} {setup.direction.upper()} -- salida: {result.exit_reason}",
        returnfig=True, figsize=(15, 8), volume=False,
    )
    if addplots:
        plot_kwargs["addplot"] = addplots
    fig, axes = mpf.plot(ohlc, **plot_kwargs)
    ax = axes[0]

    if zone_bottom is not None:
        zone_color = "green" if setup.direction == "long" else "red"
        ax.axhspan(zone_bottom, zone_top, color=zone_color, alpha=0.20, label="FVG (desequilibrio)")

    def hline(y, color, style, label):
        ax.axhline(y, color=color, linestyle=style, linewidth=1.3)
        ax.text(len(window) - 1, y, f" {label}", va="center", fontsize=8, color=color,
                fontweight="bold", clip_on=False)

    hline(setup.stop_price, "darkred", "--", "STOP")
    hline(setup.entry_price_target, "black", "-", "ENTRADA")
    hline(setup.take_profit_price, "darkgreen", "--", "TP (1:2)")

    entry_dt = setup.signal_datetime
    if entry_dt in window.index:
        marker = "^" if setup.direction == "long" else "v"
        ax.scatter([window.index.get_loc(entry_dt)], [setup.entry_price_target],
                   marker=marker, s=200, color="blue", zorder=5, edgecolors="black",
                   label="apertura de la posición")

    if result.exit_datetime in window.index:
        exit_color = {"take_profit": "green", "stop_loss": "red", "time_exit": "gray"}.get(result.exit_reason, "gray")
        ax.scatter([window.index.get_loc(result.exit_datetime)], [result.exit_price],
                   marker="x", s=180, color=exit_color, zorder=5, linewidths=3,
                   label=f"salida ({result.exit_reason})")

    ax.legend(loc="upper left", fontsize=8, framealpha=0.9)

    safe_tag = "vieja" if tag.startswith("VIEJA") else "nueva"
    path = os.path.join(config.RESULTS_DIR, f"amzn_{safe_tag}_{idx}_{result.exit_reason}.png")
    fig.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(fig)
    print(f"Guardado: {path}")


def main():
    os.makedirs(config.RESULTS_DIR, exist_ok=True)
    config.TP_RR_RATIO = CFG["tp_rr_ratio"]
    df_entry, df_context = load(SYMBOL)

    baseline_setups = generate_setups(
        SYMBOL, df_context.copy(), df_entry.copy(), min_swing_percentile=CFG["percentile"],
        use_trend_filter=CFG["use_trend_filter"], use_session_filter=CFG["use_session_filter"],
        require_regime=CFG["require_regime"],
    )
    _, _, df_entry_p, _ = prepare(df_context.copy(), df_entry.copy(), min_swing_percentile=CFG["percentile"])

    df_entry_ind = add_ema(df_entry.copy(), 10, "ema10")
    df_entry_ind["ema10_bias"] = ema_simple_bias(df_entry_ind, "ema10")
    new_setups = []
    for s in baseline_setups:
        required_bias = "up" if s.direction == "long" else "down"
        if df_entry_ind["ema10_bias"].iloc[s.signal_bar_pos] == required_bias:
            new_setups.append(s)

    baseline_results = simulate_trades(baseline_setups, df_entry, config.INITIAL_CAPITAL_USDT)
    new_results = simulate_trades(new_setups, df_entry, config.INITIAL_CAPITAL_USDT)

    def last_n_pairs(setups, results, n):
        pairs = []
        for r in results:
            s = next((s for s in setups if s.signal_datetime == r.entry_datetime and s.direction == r.direction), None)
            if s:
                pairs.append((s, r))
        return pairs[-n:]

    print(f"\nVIEJA (sin filtro): {len(baseline_results)} trades totales, graficando las últimas {N_EXAMPLES}")
    for idx, (setup, result) in enumerate(last_n_pairs(baseline_setups, baseline_results, N_EXAMPLES), start=1):
        plot_trade(df_entry, df_entry_p, setup, result, idx, "VIEJA (sin filtro)")

    print(f"\nNUEVA (EMA10): {len(new_results)} trades totales, graficando las últimas {N_EXAMPLES}")
    for idx, (setup, result) in enumerate(last_n_pairs(new_setups, new_results, N_EXAMPLES), start=1):
        plot_trade(df_entry, df_entry_p, setup, result, idx, "NUEVA (EMA10)")


if __name__ == "__main__":
    main()
