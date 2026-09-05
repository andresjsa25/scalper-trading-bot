"""
Barrido de calibración de src/strategy_v8_rsi_confluence.py sobre los 10
símbolos de config.SYMBOLS (1h, ~1.5 años de historia). Pedido explícito
del usuario (2026-08-25): no busca "la más rentable en 1 activo", busca la
configuración más CONSISTENTE (rentable en la mayor cantidad de activos
posible) y que sea fácil de explicar/aplicar a mano -- por eso se prioriza
"símbolos rentables" por sobre el profit factor agregado puro (un PF alto
sostenido por 1-2 símbolos con muestra chica no es una estrategia
aplicable, es ruido).

Grilla:
  mode            : pullback, reversal
  rsi_ob          : 70, 75, 80
  rsi_os          : 30, 25, 20
  require_bb_touch, require_macd_turn, require_volume, require_adx: True/False (16 combinaciones)
  rr_ratio        : 1.5, 2.0, 2.5
Total: 2 x 3 x 3 x 16 x 3 = 864 configuraciones x 10 símbolos.

Optimización: los indicadores (RSI/MACD/Bollinger/ADX/volumen) se calculan
UNA sola vez por símbolo (prepare_base), no en cada una de las 864
combinaciones -- lo único que cambia entre combinaciones son los umbrales
sobre columnas ya calculadas (generate_setups_from_prepared).

Filtro de confianza: se descartan configuraciones con menos de MIN_TRADES_TOTAL
operaciones sumando los 10 símbolos (con pocas operaciones el profit factor
no significa nada, es prácticamente una moneda al aire).

Salidas:
  results/v8_calibration_all.csv   -- una fila por (configuración, símbolo)
  results/v8_calibration_best.csv  -- una fila por configuración, agregado
                                       across símbolos, ordenado por
                                       consistencia y luego profit factor
"""
import itertools
import os
import sys

import pandas as pd

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
import config
from strategy_v8_rsi_confluence import prepare_base, generate_setups_from_prepared
from backtest import simulate_trades, compute_metrics

DISPLAY = {
    "BTC/USDT:USDT": "BTC", "ETH/USDT:USDT": "ETH", "XAUT/USDT:USDT": "XAUT",
    "NCSISP5002USD/USDT:USDT": "SP500/USD", "NCSINASDAQ1002USD/USDT:USDT": "NASDAQ100/USD",
    "NCCO1OILBRENT2USD/USDT:USDT": "OIL_BRENT/USD", "NCCOXAG2USD/USDT:USDT": "SILVER/USD",
    "HYPE/USDT:USDT": "HYPE", "NCSKAAPL2USD/USDT:USDT": "AAPL/USD", "NCSKAMZN2USD/USDT:USDT": "AMZN/USD",
}

# Filtrado por línea de comandos (python3 run_calibrate_v8_rsi_confluence.py pullback|reversal):
# el sandbox donde corre esto tiene un tope de tiempo por comando (~170s), y barrer los
# 2 modos completos en una sola corrida lo supera. Se corre un modo a la vez y se combinan
# los CSV al final con combine_v8_calibration.py -- no cambia la lógica del barrido, solo
# cómo se reparte en el tiempo.
MODES = ["pullback", "reversal"]
RSI_OB_VALUES = [70, 75, 80]
RSI_OS_VALUES = [30, 25, 20]
TOGGLE_COMBOS = list(itertools.product([True, False], repeat=4))  # (bb_touch, macd_turn, volume, adx)
RR_RATIOS = [2.0]  # primera pasada amplia con rr fijo (ver docstring) -- se afina rr aparte sobre las mejores config

OUTPUT_SUFFIX = ""
if len(sys.argv) > 1 and sys.argv[1] in MODES:
    MODES = [sys.argv[1]]
    OUTPUT_SUFFIX = f"_{sys.argv[1]}"
if len(sys.argv) > 2:
    rsi_ob_filter = int(sys.argv[2])
    RSI_OB_VALUES = [rsi_ob_filter]
    OUTPUT_SUFFIX += f"_ob{rsi_ob_filter}"

MIN_TRADES_TOTAL = 30  # umbral mínimo de confianza -- por debajo, se descarta del ranking (no del CSV completo)


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
        if len(df_1h) == 0 or len(df_4h) == 0:
            print(f"[!] {symbol}: algún timeframe está vacío, se salta.")
            continue
        _, df_1h_prepared = prepare_base(df_4h, df_1h)
        prepared_by_symbol[symbol] = df_1h_prepared
        print(f"Preparado: {DISPLAY.get(symbol, symbol)} ({len(df_1h)} velas de 1h)")

    all_rows = []
    combo_id = 0
    total_combos = len(MODES) * len(RSI_OB_VALUES) * len(RSI_OS_VALUES) * len(TOGGLE_COMBOS) * len(RR_RATIOS)

    for mode in MODES:
        for rsi_ob in RSI_OB_VALUES:
            for rsi_os in RSI_OS_VALUES:
                for (bb_touch, macd_turn, volume, adx) in TOGGLE_COMBOS:
                    for rr in RR_RATIOS:
                        combo_id += 1
                        for symbol, df_1h_prepared in prepared_by_symbol.items():
                            setups = generate_setups_from_prepared(
                                symbol, df_1h_prepared, mode=mode, rsi_ob=rsi_ob, rsi_os=rsi_os,
                                require_bb_touch=bb_touch, require_macd_turn=macd_turn,
                                require_volume=volume, require_adx=adx, rr_ratio=rr,
                            )
                            results = simulate_trades(setups, df_1h_prepared, config.INITIAL_CAPITAL_USDT)
                            metrics = compute_metrics(results, config.INITIAL_CAPITAL_USDT)
                            all_rows.append({
                                "combo_id": combo_id, "symbol": DISPLAY.get(symbol, symbol), "mode": mode,
                                "rsi_ob": rsi_ob, "rsi_os": rsi_os, "require_bb_touch": bb_touch,
                                "require_macd_turn": macd_turn, "require_volume": volume, "require_adx": adx,
                                "rr_ratio": rr, "num_trades": metrics["num_trades"], "win_rate": metrics["win_rate"],
                                "profit_factor": metrics["profit_factor"], "pnl_net_total": metrics.get(
                                    "final_capital", config.INITIAL_CAPITAL_USDT) - config.INITIAL_CAPITAL_USDT,
                                "max_drawdown_pct": metrics["max_drawdown_pct"],
                            })
                        if combo_id % 50 == 0:
                            print(f"  ... {combo_id}/{total_combos} configuraciones evaluadas")

    df_all = pd.DataFrame(all_rows)
    df_all.to_csv(os.path.join(config.RESULTS_DIR, f"v8_calibration_all{OUTPUT_SUFFIX}.csv"), index=False)
    print(f"\nTotal filas (config x símbolo): {len(df_all)}")

    # --- agregado por configuración, across los 10 símbolos ---
    group_cols = ["mode", "rsi_ob", "rsi_os", "require_bb_touch", "require_macd_turn",
                  "require_volume", "require_adx", "rr_ratio"]
    agg_rows = []
    for keys, grp in df_all.groupby(group_cols):
        total_trades = grp["num_trades"].sum()
        pnl_total = grp["pnl_net_total"].sum()
        symbols_profitable = (grp["pnl_net_total"] > 0).sum()
        symbols_total = grp["symbol"].nunique()
        # profit factor pooled (aprox): reconstruido desde pnl_net_total no es exacto sin el detalle de cada trade,
        # así que se reporta el promedio de profit_factor de los símbolos con operaciones, y por separado el pnl total
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
    df_agg_confiable.to_csv(os.path.join(config.RESULTS_DIR, f"v8_calibration_best{OUTPUT_SUFFIX}.csv"), index=False)
    df_agg.to_csv(os.path.join(config.RESULTS_DIR, f"v8_calibration_all_aggregated{OUTPUT_SUFFIX}.csv"), index=False)

    print(f"\nConfiguraciones con >= {MIN_TRADES_TOTAL} operaciones totales: {len(df_agg_confiable)} de {len(df_agg)}")
    print("\n=== TOP 15 por consistencia (símbolos rentables) y luego profit factor ===")
    print(df_agg_confiable.head(15).to_string(index=False))
    print(f"\nGuardado en results/v8_calibration_all{OUTPUT_SUFFIX}.csv, "
          f"results/v8_calibration_best{OUTPUT_SUFFIX}.csv y "
          f"results/v8_calibration_all_aggregated{OUTPUT_SUFFIX}.csv")


if __name__ == "__main__":
    main()
