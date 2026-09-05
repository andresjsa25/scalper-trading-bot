"""
Toma los 5 activos que hoy corren con V5 (Fibonacci pullback, 1h/4h) y los
backtestea con la estrategia V1 (Sniper de liquidez, 15m/1h) para comparar
si les va mejor.

IMPORTANTE: estos 5 símbolos nunca se calibraron para V1 (V1_LIVE_CONFIG
solo tiene SILVER/SP500/NASDAQ100/OIL_BRENT/XAUT/AMZN/ADA/BNB). No hay un
ajuste por símbolo "validado" para copiar acá, así que se usan los
DEFAULTS del módulo strategy_v1_sniper.py tal cual (sin elegir a dedo):
  min_swing_percentile=0, use_trend_filter=False, use_session_filter=True,
  require_regime=None, tp_rr_ratio=2.0 (default de config.py),
  ema_filter="ema_only" (el modo más simple de entry_filters.py, no el
  híbrido con T-Theory que solo se calibró para SILVER/OIL_BRENT/ADA).
Esto es intencionalmente una comparación "sin calibrar vs sin calibrar" --
si después de esto V1 gana, recién ahí tendría sentido invertir tiempo en
calibrar por símbolo como se hizo con los otros 8.
"""
import os
import sys

import pandas as pd

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
import config
from strategy_v1_sniper import generate_setups as generate_setups_v1
from entry_filters import apply_entry_filter
from backtest import simulate_trades, compute_metrics

SYMBOLS = [
    "NCSKAAPL2USD/USDT:USDT", "ETH/USDT:USDT", "BTC/USDT:USDT",
    "HYPE/USDT:USDT", "SOL/USDT:USDT",
]
DISPLAY_NAME = {
    "NCSKAAPL2USD/USDT:USDT": "AAPL/USD", "ETH/USDT:USDT": "ETH",
    "BTC/USDT:USDT": "BTC", "HYPE/USDT:USDT": "HYPE", "SOL/USDT:USDT": "SOL",
}

# Defaults de strategy_v1_sniper.py / config.py, sin calibrar por símbolo.
TP_RR_RATIO = 2.0
EMA_FILTER = "ema_only"


def load(symbol):
    fname = symbol.replace("/", "_").replace(":", "_")
    df_entry = pd.read_csv(os.path.join(config.DATA_DIR, f"{fname}_15m.csv"))
    df_context = pd.read_csv(os.path.join(config.DATA_DIR, f"{fname}_1h.csv"))
    df_entry["datetime"] = pd.to_datetime(df_entry["datetime"], utc=True)
    df_context["datetime"] = pd.to_datetime(df_context["datetime"], utc=True)
    return df_entry, df_context


def main():
    os.makedirs(config.RESULTS_DIR, exist_ok=True)
    rows = []
    config.TP_RR_RATIO = TP_RR_RATIO

    for symbol in SYMBOLS:
        fname = symbol.replace("/", "_").replace(":", "_")
        path = os.path.join(config.DATA_DIR, f"{fname}_15m.csv")
        if not os.path.exists(path):
            print(f"[!] Sin datos de 15m para {symbol}, se salta")
            continue

        df_entry, df_context = load(symbol)
        days = (df_entry["datetime"].max() - df_entry["datetime"].min()).total_seconds() / 86400

        setups = generate_setups_v1(symbol, df_context, df_entry)  # todos los defaults del módulo
        setups = apply_entry_filter(setups, df_entry, EMA_FILTER)

        results = simulate_trades(setups, df_entry, config.INITIAL_CAPITAL_USDT)
        metrics = compute_metrics(results, config.INITIAL_CAPITAL_USDT)
        metrics["symbol"] = symbol
        metrics["display_name"] = DISPLAY_NAME.get(symbol, symbol)
        metrics["trades_per_day"] = metrics["num_trades"] / days if days > 0 else 0
        metrics["days_analizados"] = round(days, 1)
        rows.append(metrics)

        print(f"{DISPLAY_NAME.get(symbol, symbol):10s} dias={days:6.1f} trades={metrics['num_trades']:4d} "
              f"trades/dia={metrics['trades_per_day']:.3f} win_rate={metrics['win_rate']:.1f}% "
              f"PF={metrics['profit_factor']:.2f} retorno={metrics['total_return_pct']:.2f}% "
              f"dd={metrics['max_drawdown_pct']:.2f}%")

    df = pd.DataFrame(rows)
    out_path = os.path.join(config.RESULTS_DIR, "v5_symbols_on_v1_summary.csv")
    df.to_csv(out_path, index=False)
    print(f"\nGuardado en {out_path}")


if __name__ == "__main__":
    main()
