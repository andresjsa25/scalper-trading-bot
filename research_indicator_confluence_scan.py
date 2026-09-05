"""
Scanner de confluencias DE A PARES entre 6 indicadores (RSI, MACD, Bandas
de Bollinger, EMA/tendencia, ADX, Volumen relativo) -- pedido explícito
del usuario (2026-08-25) después de que exigir 4-5 confluencias a la vez
(strategy_v7_confluence.py, strategy_v8_rsi_confluence.py) dejara muestras
demasiado chicas para confiar en el resultado (40-150 operaciones en 1.5
años).

Esto NO es un backtest con stop/TP -- es un análisis de PODER PREDICTIVO
DIRECCIONAL: para cada patrón (un indicador "ancla" que dispara un evento,
más un segundo indicador que confirma su estado en ese momento), se mide
qué pasa con el precio en las siguientes 1/2/4 horas (o 4/8h si el ancla
es de 4h), comparado contra un umbral de costos (~0.15%, aprox. comisiones
+ slippage ida y vuelta de config.py) para no contar como "acierto" un
movimiento tan chico que las comisiones ya se lo comen. Una vez que se
identifica qué par + temporalidad tiene un poder predictivo real y
consistente entre los 10 símbolos, ESE patrón se traduce recién ahí a una
estrategia con gestión de riesgo (TradeSetup, stop, TP) para backtestear
de verdad -- no antes, para no gastar tiempo calibrando gestión de riesgo
sobre un patrón que ni siquiera predice nada.

3 anclas (eventos puntuales, disparan en UNA vela):
  - rsi   : detect_rsi_extreme_exit (RSI vuelve a cruzar 70/30)
  - macd  : add_macd_turning (histograma empieza a girar)
  - bb    : detect_bb_reclaim (mecha por fuera de la banda, cierre de vuelta adentro)

Confirmadores direccionales (se lee su ESTADO en la misma vela del ancla,
no se le exige que también dispare un evento):
  - rsi (>50 / <50), macd (línea sobre/bajo señal), bb (precio sobre/bajo
    la media móvil central), ema (sesgo de tendencia)

Confirmadores de "filtro" (no direccionales, solo se exige que estén
activos, sin importar si el ancla es alcista o bajista):
  - adx (>=20, hay tendencia real) / volumen relativo (>=1, participación real)

3 pasadas de temporalidad:
  A) ancla en 1h, confirmador leído en 1h (misma vela)
  B) ancla en 1h, confirmador leído en 4h (el último valor de 4h conocido a esa hora)
  C) ancla en 4h, confirmador leído en 4h (ambos nativos de 4h)

Salida: results/confluence_scan_all.csv (una fila por símbolo x configuración)
y results/confluence_scan_ranked.csv (agregado, ordenado por consistencia
-- símbolos con hit-rate>55% -- y luego por hit-rate agrupado).
"""
import os
import sys

import pandas as pd

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "src", "indicators"))
import config
from indicators.trend import add_ema, ema_bias, add_adx
from indicators.momentum import add_rsi, add_macd, add_macd_turning, detect_rsi_extreme_exit
from indicators.volatility import add_bollinger_bands, detect_bb_reclaim
from indicators.volume import add_relative_volume

DISPLAY = {
    "BTC/USDT:USDT": "BTC", "ETH/USDT:USDT": "ETH", "XAUT/USDT:USDT": "XAUT",
    "NCSISP5002USD/USDT:USDT": "SP500/USD", "NCSINASDAQ1002USD/USDT:USDT": "NASDAQ100/USD",
    "NCCO1OILBRENT2USD/USDT:USDT": "OIL_BRENT/USD", "NCCOXAG2USD/USDT:USDT": "SILVER/USD",
    "HYPE/USDT:USDT": "HYPE", "NCSKAAPL2USD/USDT:USDT": "AAPL/USD", "NCSKAMZN2USD/USDT:USDT": "AMZN/USD",
}

COST_BUFFER = 0.0015  # ~0.15%: TAKER_FEE_PCT x2 + SLIPPAGE_PCT_ESTIMATE x2 (config.py), redondeado hacia arriba
RSI_OB, RSI_OS = 70, 30  # fijos en esta pasada exploratoria (no se barren -- ver docstring)

EVENT_COLS = {
    "rsi": ("rsi_exit_oversold", "rsi_exit_overbought"),
    "macd": ("macd_turning_up", "macd_turning_down"),
    "bb": ("bb_reclaim_bull", "bb_reclaim_bear"),
}
STATE_COLS = {
    "rsi": ("rsi_bull_state", "rsi_bear_state"),
    "macd": ("macd_bull_state", "macd_bear_state"),
    "bb": ("bb_bull_state", "bb_bear_state"),
    "ema": ("ema_bull_state", "ema_bear_state"),
}
GATE_COLS = {"adx": "adx_gate", "vol": "vol_gate"}


def load_df(symbol: str, tf: str) -> pd.DataFrame:
    fname = symbol.replace("/", "_").replace(":", "_")
    path = os.path.join(config.DATA_DIR, f"{fname}_{tf}.csv")
    df = pd.read_csv(path)
    df["datetime"] = pd.to_datetime(df["datetime"], utc=True)
    return df


def build_indicator_bundle(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = add_rsi(df, 14, "rsi")
    df = detect_rsi_extreme_exit(df, "rsi", RSI_OB, RSI_OS)
    df = add_macd(df, 12, 26, 9)
    df = add_macd_turning(df)
    df = add_bollinger_bands(df, 20, 2.0)
    df = detect_bb_reclaim(df)
    df = add_ema(df, 100, "ema_trend")
    df["bias"] = ema_bias(df, "ema_trend")
    df = add_adx(df, 14, "adx")
    df = add_relative_volume(df, 20)

    df["rsi_bull_state"] = df["rsi"] > 50
    df["rsi_bear_state"] = df["rsi"] < 50
    df["macd_bull_state"] = df["macd_line"] > df["macd_signal"]
    df["macd_bear_state"] = df["macd_line"] < df["macd_signal"]
    df["bb_bull_state"] = df["close"] > df["bb_mid"]
    df["bb_bear_state"] = df["close"] < df["bb_mid"]
    df["ema_bull_state"] = df["bias"] == "up"
    df["ema_bear_state"] = df["bias"] == "down"
    df["adx_gate"] = df["adx"] >= 20
    df["vol_gate"] = df["rel_volume"] >= 1.0
    return df.reset_index(drop=True)


def hit_stats(df: pd.DataFrame, mask_bull: pd.Series, mask_bear: pd.Series, horizon: int) -> dict:
    fwd_ret = df["close"].shift(-horizon) / df["close"] - 1
    bull_ret = fwd_ret[mask_bull.fillna(False)].dropna()
    bear_ret = fwd_ret[mask_bear.fillna(False)].dropna()

    # correcto: señal alcista y el precio sube más que el buffer de costos (o al revés para bajista).
    # incorrecto: se mueve más que el buffer PERO en contra de la señal.
    # lo que se mueve menos que el buffer en cualquier dirección se descarta (empataría con comisiones).
    correct = int((bull_ret > COST_BUFFER).sum() + (bear_ret < -COST_BUFFER).sum())
    wrong = int((bull_ret < -COST_BUFFER).sum() + (bear_ret > COST_BUFFER).sum())
    n_signals = len(bull_ret) + len(bear_ret)
    n_conclusive = correct + wrong

    return {
        "n_signals": n_signals, "n_conclusive": n_conclusive,
        "hit_rate": round(correct / n_conclusive * 100, 1) if n_conclusive > 0 else float("nan"),
        "avg_ret_aligned_pct": round(
            (pd.concat([bull_ret, -bear_ret]).mean() * 100) if n_signals > 0 else float("nan"), 3
        ),
    }


def main():
    os.makedirs(config.RESULTS_DIR, exist_ok=True)
    rows = []

    for symbol in config.SYMBOLS:
        try:
            df_1h_raw = load_df(symbol, "1h")
            df_4h_raw = load_df(symbol, "4h")
        except FileNotFoundError as e:
            print(f"[!] {symbol}: falta un archivo de datos ({e}), se salta.")
            continue

        df_1h = build_indicator_bundle(df_1h_raw)
        df_4h = build_indicator_bundle(df_4h_raw)
        display = DISPLAY.get(symbol, symbol)

        confirmer_4h_cols = list(STATE_COLS.values())
        confirmer_4h_flat = [c for pair in confirmer_4h_cols for c in pair] + list(GATE_COLS.values())
        df_4h_confirm = df_4h[["datetime"] + confirmer_4h_flat].rename(
            columns={c: f"{c}_4h" for c in confirmer_4h_flat}
        )
        df_1h_with_4h = pd.merge_asof(
            df_1h.sort_values("datetime"), df_4h_confirm.sort_values("datetime"),
            on="datetime", direction="backward",
        ).reset_index(drop=True)

        # --- PASE A: ancla 1h, confirmador 1h ---
        for anchor, (a_bull, a_bear) in EVENT_COLS.items():
            for horizon in (1, 2, 4):
                base = hit_stats(df_1h, df_1h[a_bull], df_1h[a_bear], horizon)
                rows.append({"pase": "A_1h_1h", "anchor": anchor, "confirmer": "(solo)",
                             "symbol": display, "horizon": horizon, **base})
                for confirmer, (c_bull, c_bear) in STATE_COLS.items():
                    if confirmer == anchor:
                        continue
                    mb = df_1h[a_bull] & df_1h[c_bull]
                    me = df_1h[a_bear] & df_1h[c_bear]
                    st = hit_stats(df_1h, mb, me, horizon)
                    rows.append({"pase": "A_1h_1h", "anchor": anchor, "confirmer": confirmer,
                                 "symbol": display, "horizon": horizon, **st})
                for gate_name, gate_col in GATE_COLS.items():
                    mb = df_1h[a_bull] & df_1h[gate_col]
                    me = df_1h[a_bear] & df_1h[gate_col]
                    st = hit_stats(df_1h, mb, me, horizon)
                    rows.append({"pase": "A_1h_1h", "anchor": anchor, "confirmer": gate_name,
                                 "symbol": display, "horizon": horizon, **st})

        # --- PASE B: ancla 1h, confirmador 4h (proyectado sobre la vela de 1h) ---
        for anchor, (a_bull, a_bear) in EVENT_COLS.items():
            for horizon in (1, 2, 4):
                for confirmer, (c_bull, c_bear) in STATE_COLS.items():
                    if confirmer == anchor:
                        continue
                    mb = df_1h_with_4h[a_bull] & df_1h_with_4h[f"{c_bull}_4h"]
                    me = df_1h_with_4h[a_bear] & df_1h_with_4h[f"{c_bear}_4h"]
                    st = hit_stats(df_1h_with_4h, mb, me, horizon)
                    rows.append({"pase": "B_1h_4h", "anchor": anchor, "confirmer": confirmer,
                                 "symbol": display, "horizon": horizon, **st})
                for gate_name, gate_col in GATE_COLS.items():
                    mb = df_1h_with_4h[a_bull] & df_1h_with_4h[f"{gate_col}_4h"]
                    me = df_1h_with_4h[a_bear] & df_1h_with_4h[f"{gate_col}_4h"]
                    st = hit_stats(df_1h_with_4h, mb, me, horizon)
                    rows.append({"pase": "B_1h_4h", "anchor": anchor, "confirmer": gate_name,
                                 "symbol": display, "horizon": horizon, **st})

        # --- PASE C: ancla 4h, confirmador 4h (nativo) ---
        for anchor, (a_bull, a_bear) in EVENT_COLS.items():
            for horizon in (1, 2):
                base = hit_stats(df_4h, df_4h[a_bull], df_4h[a_bear], horizon)
                rows.append({"pase": "C_4h_4h", "anchor": anchor, "confirmer": "(solo)",
                             "symbol": display, "horizon": horizon, **base})
                for confirmer, (c_bull, c_bear) in STATE_COLS.items():
                    if confirmer == anchor:
                        continue
                    mb = df_4h[a_bull] & df_4h[c_bull]
                    me = df_4h[a_bear] & df_4h[c_bear]
                    st = hit_stats(df_4h, mb, me, horizon)
                    rows.append({"pase": "C_4h_4h", "anchor": anchor, "confirmer": confirmer,
                                 "symbol": display, "horizon": horizon, **st})
                for gate_name, gate_col in GATE_COLS.items():
                    mb = df_4h[a_bull] & df_4h[gate_col]
                    me = df_4h[a_bear] & df_4h[gate_col]
                    st = hit_stats(df_4h, mb, me, horizon)
                    rows.append({"pase": "C_4h_4h", "anchor": anchor, "confirmer": gate_name,
                                 "symbol": display, "horizon": horizon, **st})

        print(f"{display:16s} listo")

    df_all = pd.DataFrame(rows)
    df_all.to_csv(os.path.join(config.RESULTS_DIR, "confluence_scan_all.csv"), index=False)
    print(f"\nTotal filas (símbolo x configuración): {len(df_all)}")

    # --- agregado por (pase, anchor, confirmer, horizon), across los 10 símbolos ---
    group_cols = ["pase", "anchor", "confirmer", "horizon"]
    agg_rows = []
    for keys, grp in df_all.groupby(group_cols):
        n_conclusive_total = grp["n_conclusive"].sum()
        symbols_hit55 = (grp["hit_rate"] > 55).sum()
        symbols_with_data = grp["hit_rate"].notna().sum()
        pooled_hit_rate = (grp["hit_rate"] * grp["n_conclusive"]).sum() / n_conclusive_total if n_conclusive_total > 0 else float("nan")
        row = dict(zip(group_cols, keys))
        row.update({
            "n_conclusive_total": n_conclusive_total, "symbols_hit_over_55pct": symbols_hit55,
            "symbols_con_datos": symbols_with_data,
            "pooled_hit_rate": round(pooled_hit_rate, 1) if pd.notna(pooled_hit_rate) else pooled_hit_rate,
            "avg_ret_aligned_pct_mean": round(grp["avg_ret_aligned_pct"].mean(), 3),
        })
        agg_rows.append(row)

    df_ranked = pd.DataFrame(agg_rows)
    MIN_N = 80
    df_ranked_confiable = df_ranked[df_ranked["n_conclusive_total"] >= MIN_N].copy()
    df_ranked_confiable = df_ranked_confiable.sort_values(
        ["symbols_hit_over_55pct", "pooled_hit_rate"], ascending=[False, False]
    )
    df_ranked_confiable.to_csv(os.path.join(config.RESULTS_DIR, "confluence_scan_ranked.csv"), index=False)
    df_ranked.to_csv(os.path.join(config.RESULTS_DIR, "confluence_scan_ranked_ALL.csv"), index=False)

    print(f"\nConfiguraciones con >= {MIN_N} señales concluyentes en total: "
          f"{len(df_ranked_confiable)} de {len(df_ranked)}")
    print("\n=== TOP 25 por consistencia (símbolos con hit-rate>55%) y luego hit-rate agrupado ===")
    print(df_ranked_confiable.head(25).to_string(index=False))
    print("\nGuardado en results/confluence_scan_all.csv, results/confluence_scan_ranked.csv "
          "y results/confluence_scan_ranked_ALL.csv")


if __name__ == "__main__":
    main()
