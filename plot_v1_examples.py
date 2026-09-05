"""
Grafica ejemplos de V1 (Sniper de liquidez) para verificar consistencia:
FVG (desequilibrio) sombreado, nivel de liquidez barrido, entrada, stop y
TP marcados. Solo LEE datos y funciones ya existentes de strategy_v1_sniper
(prepare, detect_fvg) -- no modifica nada del bot en vivo.
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mplfinance as mpf
import pandas as pd

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
import config
from strategy_v1_sniper import generate_setups, prepare
from backtest import simulate_trades, compute_metrics

# símbolo -> config final (run_v1_final.py) para los activos asignados a V1
V1_CONFIGS = {
    "XAUT/USDT:USDT": {"percentile": 0, "use_trend_filter": True, "use_session_filter": False,
                        "require_regime": None, "tp_rr_ratio": 2.0},
    "NCSISP5002USD/USDT:USDT": {"percentile": 20, "use_trend_filter": False, "use_session_filter": True,
                                 "require_regime": None, "tp_rr_ratio": 2.0},
    "NCSINASDAQ1002USD/USDT:USDT": {"percentile": 0, "use_trend_filter": False, "use_session_filter": True,
                                     "require_regime": None, "tp_rr_ratio": 2.0},
    "NCCO1OILBRENT2USD/USDT:USDT": {"percentile": 0, "use_trend_filter": False, "use_session_filter": True,
                                     "require_regime": None, "tp_rr_ratio": 2.0},
    "NCSKAMZN2USD/USDT:USDT": {"percentile": 0, "use_trend_filter": False, "use_session_filter": True,
                                "require_regime": None, "tp_rr_ratio": 2.0},
}
DISPLAY_NAME = {
    "XAUT/USDT:USDT": "XAUT", "NCSISP5002USD/USDT:USDT": "SP500/USD",
    "NCSINASDAQ1002USD/USDT:USDT": "NASDAQ100/USD", "NCCO1OILBRENT2USD/USDT:USDT": "OIL_BRENT/USD",
    "NCSKAMZN2USD/USDT:USDT": "AMZN/USD",
}
BARS_BEFORE = 20
BARS_AFTER = 10


def load(symbol):
    fname = symbol.replace("/", "_").replace(":", "_")
    df_entry = pd.read_csv(os.path.join(config.DATA_DIR, f"{fname}_{config.TIMEFRAME_ENTRY}.csv"))
    df_context = pd.read_csv(os.path.join(config.DATA_DIR, f"{fname}_{config.TIMEFRAME_CONTEXT}.csv"))
    df_entry["datetime"] = pd.to_datetime(df_entry["datetime"], utc=True)
    df_context["datetime"] = pd.to_datetime(df_context["datetime"], utc=True)
    return df_entry, df_context


def find_fvg_zone(df_entry_enriched, setup):
    """Ubica el FVG que originó la entrada: entry_price_target es EXACTAMENTE
    fvg_bottom (corto) o fvg_top (largo) de la vela del desequilibrio."""
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


def plot_trade(symbol, cfg, df_entry, df_context, setup, result, idx):
    df_context_p, context_sweeps, df_entry_p, entry_swings = prepare(
        df_context.copy(), df_entry.copy(), min_swing_percentile=cfg["percentile"])
    zone_bottom, zone_top = find_fvg_zone(df_entry_p, setup)

    entry_pos = int(df_entry["datetime"].searchsorted(setup.signal_datetime))
    exit_pos = int(df_entry["datetime"].searchsorted(result.exit_datetime))
    start_pos = max(0, entry_pos - BARS_BEFORE)
    end_pos = min(len(df_entry) - 1, exit_pos + BARS_AFTER)

    window = df_entry.iloc[start_pos:end_pos + 1].copy()
    window = window.set_index(pd.DatetimeIndex(window["datetime"]))
    ohlc = window[["open", "high", "low", "close", "volume"]]

    fig, axes = mpf.plot(
        ohlc, type="candle", style="charles",
        title=f"V1 #{idx} {DISPLAY_NAME.get(symbol, symbol)} {setup.direction.upper()} -- salida: {result.exit_reason}",
        returnfig=True, figsize=(15, 8), volume=False,
    )
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
    hline(setup.take_profit_price, "darkgreen", "--", f"TP (1:{cfg['tp_rr_ratio']:.0f})")

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

    safe_name = DISPLAY_NAME.get(symbol, symbol).replace("/", "-")
    path = os.path.join(config.RESULTS_DIR, f"v1_example_{idx}_{safe_name}_{result.exit_reason}.png")
    fig.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(fig)
    print(f"Guardado: {path}")


def main():
    os.makedirs(config.RESULTS_DIR, exist_ok=True)
    idx = 0
    for symbol, cfg in V1_CONFIGS.items():
        df_entry, df_context = load(symbol)
        config.TP_RR_RATIO = cfg["tp_rr_ratio"]
        setups = generate_setups(
            symbol, df_context, df_entry,
            min_swing_percentile=cfg["percentile"], use_trend_filter=cfg["use_trend_filter"],
            use_session_filter=cfg["use_session_filter"], require_regime=cfg["require_regime"],
        )
        results = simulate_trades(setups, df_entry, config.INITIAL_CAPITAL_USDT)
        if not results:
            continue
        # una ganadora (TP) y una perdedora (SL) por activo, si hay
        picked = []
        for reason in ["take_profit", "stop_loss"]:
            for r in results:
                s = next((s for s in setups if s.signal_datetime == r.entry_datetime and s.direction == r.direction), None)
                if s and r.exit_reason == reason:
                    picked.append((s, r))
                    break
        for setup, result in picked:
            idx += 1
            plot_trade(symbol, cfg, df_entry, df_context, setup, result, idx)
        if idx >= 6:
            break


if __name__ == "__main__":
    main()
