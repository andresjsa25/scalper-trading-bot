"""
Calibración de src/strategy_v10_bb_rsi_refined.py sobre los 10 símbolos de
config.SYMBOLS. rr_ratio queda FIJO en 2.0 (pedido del usuario: "si
arriesgamos 1 tenemos que ganar 2") -- lo que se barre es el STOP:

  - stop_mode="atr":  atr_mult en ATR_MULTS, por símbolo (mismo criterio
                       que V1_LIVE_CONFIG: cada símbolo puede tener su
                       propio múltiplo óptimo).
  - stop_mode="wick": wick_buffer_atr_frac en WICK_BUFFER_FRACS.

Cada combinación se corre además con require_pattern=True y False, para
comparar con y sin el filtro de patrón de vela (pedido explícito del
usuario: no asumir que ayuda, medirlo).

Los indicadores (Bollinger/RSI/ATR/patrones de vela) se calculan UNA sola
vez por símbolo (prepare()), no en cada combinación -- solo cambian los
parámetros de stop y el filtro sobre columnas ya calculadas.
"""
import os
import sys

import pandas as pd

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
import config
from strategy_v10_bb_rsi_refined import prepare, generate_setups_from_prepared
from backtest import simulate_trades, compute_metrics

DISPLAY = {
    "BTC/USDT:USDT": "BTC", "ETH/USDT:USDT": "ETH", "XAUT/USDT:USDT": "XAUT",
    "NCSISP5002USD/USDT:USDT": "SP500/USD", "NCSINASDAQ1002USD/USDT:USDT": "NASDAQ100/USD",
    "NCCO1OILBRENT2USD/USDT:USDT": "OIL_BRENT/USD", "NCCOXAG2USD/USDT:USDT": "SILVER/USD",
    "HYPE/USDT:USDT": "HYPE", "NCSKAAPL2USD/USDT:USDT": "AAPL/USD", "NCSKAMZN2USD/USDT:USDT": "AMZN/USD",
}

ATR_MULTS = [1.0, 1.2, 1.5, 1.8, 2.0, 2.5, 3.0]
WICK_BUFFER_FRACS = [0.0, 0.1, 0.2, 0.3]
REQUIRE_PATTERN_VALUES = [False, True]
RR_RATIO = 2.0
MIN_TRADES_TOTAL = 30


def load_df(symbol: str, tf: str) -> pd.DataFrame:
    fname = symbol.replace("/", "_").replace(":", "_")
    path = os.path.join(config.DATA_DIR, f"{fname}_{tf}.csv")
    df = pd.read_csv(path)
    df["datetime"] = pd.to_datetime(df["datetime"], utc=True)
    return df


def main():
    os.makedirs(config.RESULTS_DIR, exist_ok=True)

    prepared_by_symbol = {}
    for symbol in config.SYMBOLS:
        try:
            df_4h = load_df(symbol, "4h")
            df_1h = load_df(symbol, "1h")
        except FileNotFoundError as e:
            print(f"[!] {symbol}: falta un archivo de datos ({e}), se salta.")
            continue
        _, df_1h_prepared = prepare(df_4h, df_1h)
        prepared_by_symbol[symbol] = df_1h_prepared
        print(f"Preparado: {DISPLAY.get(symbol, symbol)} ({len(df_1h)} velas de 1h)")

    all_rows = []
    combo_id = 0

    combos = []
    for atr_mult in ATR_MULTS:
        for req_pattern in REQUIRE_PATTERN_VALUES:
            combos.append(("atr", atr_mult, None, req_pattern))
    for wick_frac in WICK_BUFFER_FRACS:
        for req_pattern in REQUIRE_PATTERN_VALUES:
            combos.append(("wick", None, wick_frac, req_pattern))

    for stop_mode, atr_mult, wick_frac, req_pattern in combos:
        combo_id += 1
        for symbol, df_prepared in prepared_by_symbol.items():
            kwargs = dict(
                stop_mode=stop_mode,
                require_pattern=req_pattern,
                rr_ratio=RR_RATIO,
            )
            if stop_mode == "atr":
                kwargs["atr_mult"] = atr_mult
            else:
                kwargs["wick_buffer_atr_frac"] = wick_frac

            setups = generate_setups_from_prepared(symbol, df_prepared, **kwargs)
            results = simulate_trades(setups, df_prepared, config.INITIAL_CAPITAL_USDT)
            metrics = compute_metrics(results, config.INITIAL_CAPITAL_USDT)
            all_rows.append({
                "combo_id": combo_id, "symbol": DISPLAY.get(symbol, symbol),
                "stop_mode": stop_mode, "atr_mult": atr_mult, "wick_buffer_frac": wick_frac,
                "require_pattern": req_pattern, "rr_ratio": RR_RATIO,
                "num_trades": metrics["num_trades"], "win_rate": metrics["win_rate"],
                "profit_factor": metrics["profit_factor"],
                "pnl_net_total": metrics.get("final_capital", config.INITIAL_CAPITAL_USDT) - config.INITIAL_CAPITAL_USDT,
                "max_drawdown_pct": metrics["max_drawdown_pct"],
            })
        print(f"  combo {combo_id}/{len(combos)} listo "
              f"(stop={stop_mode}, atr_mult={atr_mult}, wick_frac={wick_frac}, pattern={req_pattern})")

    df_all = pd.DataFrame(all_rows)
    df_all.to_csv(os.path.join(config.RESULTS_DIR, "v10_calibration_all.csv"), index=False)
    print(f"\nTotal filas (config x símbolo): {len(df_all)}")

    # --- agregado por configuración, across los 10 símbolos ---
    group_cols = ["stop_mode", "atr_mult", "wick_buffer_frac", "require_pattern", "rr_ratio"]
    agg_rows = []
    for keys, grp in df_all.groupby(group_cols, dropna=False):
        total_trades = grp["num_trades"].sum()
        pnl_total = grp["pnl_net_total"].sum()
        symbols_profitable = (grp["pnl_net_total"] > 0).sum()
        symbols_total = grp["symbol"].nunique()
        pf_values = grp.loc[grp["num_trades"] > 0, "profit_factor"].replace([float("inf")], pd.NA).dropna()
        avg_pf = pf_values.mean() if len(pf_values) else float("nan")
        win_rate_weighted = (grp["win_rate"] * grp["num_trades"]).sum() / total_trades if total_trades > 0 else float("nan")
        row = dict(zip(group_cols, keys))
        row.update({
            "total_trades": total_trades, "symbols_profitable": symbols_profitable, "symbols_total": symbols_total,
            "pnl_net_total": round(pnl_total, 2), "avg_profit_factor": round(avg_pf, 2) if pd.notna(avg_pf) else avg_pf,
            "win_rate_weighted": round(win_rate_weighted, 1),
            "max_drawdown_worst_pct": grp["max_drawdown_pct"].min(),
        })
        agg_rows.append(row)

    df_agg = pd.DataFrame(agg_rows)
    df_agg_confiable = df_agg[df_agg["total_trades"] >= MIN_TRADES_TOTAL].copy()
    df_agg_confiable = df_agg_confiable.sort_values(
        ["symbols_profitable", "avg_profit_factor"], ascending=[False, False]
    )
    df_agg_confiable.to_csv(os.path.join(config.RESULTS_DIR, "v10_calibration_best.csv"), index=False)
    df_agg.to_csv(os.path.join(config.RESULTS_DIR, "v10_calibration_all_aggregated.csv"), index=False)

    print(f"\nConfiguraciones con >= {MIN_TRADES_TOTAL} operaciones totales: {len(df_agg_confiable)} de {len(df_agg)}")
    print("\n=== TOP 20 por consistencia (símbolos rentables) y luego profit factor ===")
    print(df_agg_confiable.head(20).to_string(index=False))


if __name__ == "__main__":
    main()
