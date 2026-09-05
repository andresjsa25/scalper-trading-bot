"""
Grafica ejemplos de V5 estilo "video": zona de entrada (61.8%-78.6%)
sombreada en verde (largo) o rojo (corto), marcador de dónde se abrió la
posición, y niveles de gestión de salida (38.2%/61.8%) etiquetados --
para comparar visualmente contra el video de BITLOBO TRADING.
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
from strategy_v5_fib_pullback import generate_setups
from backtest_v5 import simulate_fib_pullback_trades

SYMBOL = "BTC/USDT:USDT"
BARS_AFTER = 15  # margen después de la salida


def load(symbol):
    fname = symbol.replace("/", "_").replace(":", "_")
    df_entry = pd.read_csv(os.path.join(config.DATA_DIR, f"{fname}_{config.TIMEFRAME_ENTRY}.csv"))
    df_context = pd.read_csv(os.path.join(config.DATA_DIR, f"{fname}_{config.TIMEFRAME_CONTEXT}.csv"))
    df_entry["datetime"] = pd.to_datetime(df_entry["datetime"], utc=True)
    df_context["datetime"] = pd.to_datetime(df_context["datetime"], utc=True)
    return df_entry, df_context


def plot_trade(df_entry, setup, result, idx):
    a_pos = int(df_entry["datetime"].searchsorted(setup.leg_a_datetime))
    start_pos = max(0, a_pos - 5)
    exit_pos = int(df_entry["datetime"].searchsorted(result.exit_datetime))
    end_pos = min(len(df_entry) - 1, exit_pos + BARS_AFTER)

    window = df_entry.iloc[start_pos:end_pos + 1].copy()
    window = window.set_index(pd.DatetimeIndex(window["datetime"]))
    ohlc = window[["open", "high", "low", "close", "volume"]]

    zone_color = "green" if setup.direction == "long" else "red"

    fig, axes = mpf.plot(
        ohlc, type="candle", style="charles",
        title=f"V5 #{idx} {setup.symbol} {setup.direction.upper()} -- salida: {result.exit_reason}",
        returnfig=True, figsize=(15, 8), volume=False,
    )
    ax = axes[0]

    # --- Zona de entrada (61.8%-78.6%), sombreada como en el video ---
    ax.axhspan(setup.zone_lower, setup.zone_upper, color=zone_color, alpha=0.18,
               label="zona de entrada (61.8%-78.6%)")

    # --- Niveles de referencia ---
    def hline(y, color, style, label):
        ax.axhline(y, color=color, linestyle=style, linewidth=1.3)
        ax.text(len(window) - 1, y, f" {label}", va="center", fontsize=8, color=color,
                fontweight="bold", clip_on=False)

    hline(setup.leg_a_price, "gray", ":", "A (0% / 100%)")
    hline(setup.a_price, "gray", ":", "B (origen del leg)")
    hline(setup.zone_886, "purple", ":", "88.6% (referencia stop)")
    hline(setup.stop_price, "darkred", "--", "STOP")
    hline(setup.entry_price_target, "black", "-", "ENTRADA")
    hline(setup.breakeven_trigger_price, "orange", "--", "38.2% (breakeven)")
    hline(setup.take_profit_price, "darkgreen", "--", "61.8% (TP)")

    # --- Marcador en la vela exacta de entrada ---
    entry_dt = setup.signal_datetime
    if entry_dt in window.index:
        marker = "^" if setup.direction == "long" else "v"
        ax.scatter([window.index.get_loc(entry_dt)], [setup.entry_price_target],
                   marker=marker, s=200, color="blue", zorder=5, edgecolors="black",
                   label="apertura de la posición")

    # --- Marcador en la vela de salida ---
    if result.exit_datetime in window.index:
        exit_color = {"take_profit": "green", "breakeven": "orange", "stop_loss": "red"}.get(
            result.exit_reason, "gray")
        ax.scatter([window.index.get_loc(result.exit_datetime)], [result.exit_price],
                   marker="x", s=180, color=exit_color, zorder=5, linewidths=3,
                   label=f"salida ({result.exit_reason})")

    ax.legend(loc="upper left", fontsize=8, framealpha=0.9)

    path = os.path.join(config.RESULTS_DIR, f"v5_example_{idx}_{result.exit_reason}.png")
    fig.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(fig)
    print(f"Guardado: {path}")
    return path


def main():
    os.makedirs(config.RESULTS_DIR, exist_ok=True)
    df_entry, df_context = load(SYMBOL)
    setups = generate_setups(SYMBOL, df_context, df_entry, min_swing_percentile=80)
    results = simulate_fib_pullback_trades(setups, df_entry, config.INITIAL_CAPITAL_USDT)

    wanted_reasons = ["take_profit", "breakeven", "stop_loss"]
    picked = []
    for reason in wanted_reasons:
        for r in results:
            setup = next((s for s in setups if s.signal_datetime == r.entry_datetime
                          and s.direction == r.direction), None)
            if setup and r.exit_reason == reason and (setup, r) not in picked:
                picked.append((setup, r))
                break

    for idx, (setup, result) in enumerate(picked[:3], start=1):
        plot_trade(df_entry, setup, result, idx)


if __name__ == "__main__":
    main()
