"""
Configuración FINAL de la Estrategia V1 (Sniper de liquidez), calibrada
por símbolo (run_calibrate_v1_per_symbol.py). 8 activos con su config
original (percentil solo, prioriza frecuencia) + XAUT con tendencia +
sin filtro de sesión (PF 0.55 -> 1.24) + BTC con tendencia + sin sesión +
régimen de volatilidad normal + TP 1:3 en vez de 1:2 (PF 1.00 -> 1.28,
32 trades). Los 10 activos del proyecto ya están representados en V1.
"""
import os
import sys

import pandas as pd

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
import config
from strategy_v1_sniper import generate_setups
from backtest import simulate_trades, compute_metrics

DISPLAY_NAME = {
    "BTC/USDT:USDT": "BTC",
    "ETH/USDT:USDT": "ETH",
    "SOL/USDT:USDT": "SOL",
    "XAUT/USDT:USDT": "XAUT",
    "NCSISP5002USD/USDT:USDT": "SP500/USD",
    "NCSINASDAQ1002USD/USDT:USDT": "NASDAQ100/USD",
    "NCCO1OILBRENT2USD/USDT:USDT": "OIL_BRENT/USD",
    "NCCOXAG2USD/USDT:USDT": "SILVER/USD",
    "HYPE/USDT:USDT": "HYPE/USD",
    "NCSKAAPL2USD/USDT:USDT": "AAPL/USD",
    "NCSKAMZN2USD/USDT:USDT": "AMZN/USD",
}

# símbolo -> {percentil, filtro de tendencia, filtro de sesión, régimen de
# volatilidad requerido, ratio TP:SL}
FINAL_CONFIG_V1 = {
    "BTC/USDT:USDT": {"percentile": 0, "use_trend_filter": True, "use_session_filter": False,
                       "require_regime": "normal", "tp_rr_ratio": 3.0},
    "ETH/USDT:USDT": {"percentile": 0, "use_trend_filter": False, "use_session_filter": True,
                       "require_regime": None, "tp_rr_ratio": 2.0},
    "XAUT/USDT:USDT": {"percentile": 0, "use_trend_filter": True, "use_session_filter": False,
                        "require_regime": None, "tp_rr_ratio": 2.0},
    "SOL/USDT:USDT": {"percentile": 0, "use_trend_filter": True, "use_session_filter": False,
                       "require_regime": None, "tp_rr_ratio": 2.0},
    "NCSISP5002USD/USDT:USDT": {"percentile": 20, "use_trend_filter": False, "use_session_filter": True,
                                 "require_regime": None, "tp_rr_ratio": 2.0},
    "NCSINASDAQ1002USD/USDT:USDT": {"percentile": 0, "use_trend_filter": False, "use_session_filter": True,
                                     "require_regime": None, "tp_rr_ratio": 2.0},
    "NCCO1OILBRENT2USD/USDT:USDT": {"percentile": 0, "use_trend_filter": False, "use_session_filter": True,
                                     "require_regime": None, "tp_rr_ratio": 2.0},
    "NCCOXAG2USD/USDT:USDT": {"percentile": 0, "use_trend_filter": False, "use_session_filter": True,
                               "require_regime": None, "tp_rr_ratio": 2.0},
    "HYPE/USDT:USDT": {"percentile": 0, "use_trend_filter": False, "use_session_filter": True,
                        "require_regime": None, "tp_rr_ratio": 2.0},
    "NCSKAAPL2USD/USDT:USDT": {"percentile": 0, "use_trend_filter": False, "use_session_filter": True,
                                "require_regime": None, "tp_rr_ratio": 2.0},
    "NCSKAMZN2USD/USDT:USDT": {"percentile": 0, "use_trend_filter": False, "use_session_filter": True,
                                "require_regime": None, "tp_rr_ratio": 2.0},
}


def load(symbol):
    fname = symbol.replace("/", "_").replace(":", "_")
    df_entry = pd.read_csv(os.path.join(config.DATA_DIR, f"{fname}_{config.TIMEFRAME_ENTRY}.csv"))
    df_context = pd.read_csv(os.path.join(config.DATA_DIR, f"{fname}_{config.TIMEFRAME_CONTEXT}.csv"))
    df_entry["datetime"] = pd.to_datetime(df_entry["datetime"], utc=True)
    df_context["datetime"] = pd.to_datetime(df_context["datetime"], utc=True)
    return df_entry, df_context


def main():
    os.makedirs(config.RESULTS_DIR, exist_ok=True)
    rows = []

    for symbol, cfg in FINAL_CONFIG_V1.items():
        config.TP_RR_RATIO = cfg["tp_rr_ratio"]
        df_entry, df_context = load(symbol)
        span_days = (df_entry["datetime"].max() - df_entry["datetime"].min()).days
        setups = generate_setups(
            symbol, df_context, df_entry,
            min_swing_percentile=cfg["percentile"],
            use_trend_filter=cfg["use_trend_filter"],
            use_session_filter=cfg["use_session_filter"],
            require_regime=cfg["require_regime"],
        )
        results = simulate_trades(setups, df_entry, config.INITIAL_CAPITAL_USDT)
        m = compute_metrics(results, config.INITIAL_CAPITAL_USDT)
        m.update({"symbol": DISPLAY_NAME[symbol], "percentile": cfg["percentile"], "tp_rr": cfg["tp_rr_ratio"],
                  "trades_per_day": m["num_trades"] / span_days if span_days else 0})
        rows.append(m)
        print(f"{DISPLAY_NAME[symbol]:15s} percentil={cfg['percentile']:3d} TP=1:{cfg['tp_rr_ratio']:.1f} "
              f"trades={m['num_trades']:4d} ({m['trades_per_day']:.3f}/día) win_rate={m['win_rate']:.1f}% "
              f"PF={m['profit_factor']:.2f} retorno={m['total_return_pct']:.2f}%")

    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(config.RESULTS_DIR, "v1_final_summary.csv"), index=False)

    total_trades = df["num_trades"].sum()
    total_trades_per_day = df["trades_per_day"].sum()
    n = len(df)
    print(f"\nTOTAL V1 ({n} activos): {total_trades} trades -> {total_trades_per_day:.2f} trades/día combinados")
    print(f"PF promedio: {df['profit_factor'].mean():.2f} | símbolos con PF>=1: {(df['profit_factor'] >= 1).sum()}/{n}")


if __name__ == "__main__":
    main()
