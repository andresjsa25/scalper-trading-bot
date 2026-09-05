"""
Rendimiento histórico de la configuración EXACTA que está corriendo en vivo
ahora mismo (V1_LIVE_CONFIG / V5_LIVE_CONFIG de run_live_trading.py) --
mismos filtros, mismo TP por símbolo, mismo apply_entry_filter. Sobre todo
el histórico disponible por símbolo (no recortado), para reflejar el
mismo backtest con el que se calibró lo que hoy opera con dinero real.
"""
import os
import sys

import pandas as pd

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
import config
from strategy_v1_sniper import generate_setups as generate_setups_v1
from strategy_v5_fib_pullback import generate_setups as generate_setups_v5
from entry_filters import apply_entry_filter
from backtest import simulate_trades, compute_metrics
from run_live_trading import V1_LIVE_CONFIG, V5_LIVE_CONFIG

DISPLAY_NAME = {
    "NCCOXAG2USD/USDT:USDT": "SILVER/USD", "NCSISP5002USD/USDT:USDT": "SP500/USD",
    "NCSINASDAQ1002USD/USDT:USDT": "NASDAQ100/USD", "NCCO1OILBRENT2USD/USDT:USDT": "OIL_BRENT/USD",
    "XAUT/USDT:USDT": "XAUT", "NCSKAMZN2USD/USDT:USDT": "AMZN/USD",
    "ADA/USDT:USDT": "ADA", "BNB/USDT:USDT": "BNB",
    "NCSKAAPL2USD/USDT:USDT": "AAPL/USD", "ETH/USDT:USDT": "ETH",
    "BTC/USDT:USDT": "BTC", "HYPE/USDT:USDT": "HYPE", "SOL/USDT:USDT": "SOL",
}


def load(symbol, tf_entry, tf_context):
    fname = symbol.replace("/", "_").replace(":", "_")
    df_entry = pd.read_csv(os.path.join(config.DATA_DIR, f"{fname}_{tf_entry}.csv"))
    df_context = pd.read_csv(os.path.join(config.DATA_DIR, f"{fname}_{tf_context}.csv"))
    df_entry["datetime"] = pd.to_datetime(df_entry["datetime"], utc=True)
    df_context["datetime"] = pd.to_datetime(df_context["datetime"], utc=True)
    return df_entry, df_context


def run_row(symbol, strategy_label, setups, df_entry, days):
    results = simulate_trades(setups, df_entry, config.INITIAL_CAPITAL_USDT)
    metrics = compute_metrics(results, config.INITIAL_CAPITAL_USDT)
    metrics["symbol"] = symbol
    metrics["display_name"] = DISPLAY_NAME.get(symbol, symbol)
    metrics["strategy"] = strategy_label
    metrics["trades_per_day"] = metrics["num_trades"] / days if days > 0 else 0
    metrics["days_analizados"] = round(days, 1)
    return metrics


def main():
    os.makedirs(config.RESULTS_DIR, exist_ok=True)
    rows = []

    print("=" * 90 + "\nV1 -- Sniper de liquidez (15m/1h)\n" + "=" * 90)
    for symbol, cfg in V1_LIVE_CONFIG.items():
        fname = symbol.replace("/", "_").replace(":", "_")
        path = os.path.join(config.DATA_DIR, f"{fname}_15m.csv")
        if not os.path.exists(path):
            print(f"[!] Sin datos para {symbol}, se salta")
            continue

        df_entry, df_context = load(symbol, "15m", "1h")
        days = (df_entry["datetime"].max() - df_entry["datetime"].min()).total_seconds() / 86400

        config.TP_RR_RATIO = cfg["tp_rr_ratio"]
        setups = generate_setups_v1(
            symbol, df_context, df_entry,
            min_swing_percentile=cfg["percentile"], use_trend_filter=cfg["use_trend_filter"],
            use_session_filter=cfg["use_session_filter"], require_regime=cfg["require_regime"],
        )
        setups = apply_entry_filter(setups, df_entry, cfg["ema_filter"])

        metrics = run_row(symbol, "V1", setups, df_entry, days)
        rows.append(metrics)
        print(f"{DISPLAY_NAME.get(symbol, symbol):15s} dias={days:6.1f} trades={metrics['num_trades']:4d} "
              f"trades/dia={metrics['trades_per_day']:.3f} win_rate={metrics['win_rate']:.1f}% "
              f"PF={metrics['profit_factor']:.2f} retorno={metrics['total_return_pct']:.2f}% "
              f"dd={metrics['max_drawdown_pct']:.2f}%")

    print("\n" + "=" * 90 + "\nV5 -- Retroceso de Fibonacci (1h/4h)\n" + "=" * 90)
    for symbol, cfg in V5_LIVE_CONFIG.items():
        fname = symbol.replace("/", "_").replace(":", "_")
        path = os.path.join(config.DATA_DIR, f"{fname}_1h.csv")
        if not os.path.exists(path):
            print(f"[!] Sin datos para {symbol}, se salta")
            continue

        df_entry, df_context = load(symbol, "1h", "4h")
        days = (df_entry["datetime"].max() - df_entry["datetime"].min()).total_seconds() / 86400

        setups = generate_setups_v5(
            symbol, df_context, df_entry,
            min_swing_percentile=cfg["percentile"], min_rr_ratio=cfg["min_rr_ratio"],
        )

        metrics = run_row(symbol, "V5", setups, df_entry, days)
        rows.append(metrics)
        print(f"{DISPLAY_NAME.get(symbol, symbol):15s} dias={days:6.1f} trades={metrics['num_trades']:4d} "
              f"trades/dia={metrics['trades_per_day']:.3f} win_rate={metrics['win_rate']:.1f}% "
              f"PF={metrics['profit_factor']:.2f} retorno={metrics['total_return_pct']:.2f}% "
              f"dd={metrics['max_drawdown_pct']:.2f}%")

    df = pd.DataFrame(rows)
    out_path = os.path.join(config.RESULTS_DIR, "live_config_performance.csv")
    df.to_csv(out_path, index=False)

    print("\n" + "=" * 90 + "\nRESUMEN POR ESTRATEGIA\n" + "=" * 90)
    agg = df.groupby("strategy").agg(
        total_trades=("num_trades", "sum"),
        avg_trades_per_day=("trades_per_day", "sum"),
        avg_win_rate=("win_rate", "mean"),
        avg_profit_factor=("profit_factor", "mean"),
        avg_return_pct=("total_return_pct", "mean"),
        avg_max_dd=("max_drawdown_pct", "mean"),
    )
    print(agg.to_string())
    print(f"\nGuardado en {out_path}")


if __name__ == "__main__":
    main()
