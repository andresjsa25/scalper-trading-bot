"""
Tearsheet completo del portafolio combinado (13 activos, capital
compartido, mismo motor que run_portfolio_simulation.py) comparando la
config real (cada símbolo con su R:R calibrado, hoy 1:2.0 todos) contra
un escenario con TODOS los símbolos forzados a 1:2.3 -- para "revisar
resultados" con ese ratio, como pidió el usuario (2026-08-08).

Métricas, con las decisiones metodológicas explícitas (no hay un único
estándar de la industria para varias de estas, así que documento qué
elegí y por qué):

  - CAGR: (capital_final/capital_inicial)^(365/días) - 1. Growth real
    compuesto, a diferencia del "retorno anualizado lineal" que usamos
    antes (ese multiplicaba el % total por 365/días, sin componer).
  - Sharpe / Sortino: sobre retornos DIARIOS del equity (resampleado a
    1D, forward-fill entre cierres), anualizados con sqrt(365) -- 365 y
    no 252 porque cripto/CFDs acá operan todos los días, no solo hábiles
    bursátiles. Tasa libre de riesgo = 0% (simplificación estándar para
    evaluar una estrategia de trading, no un fondo comparado contra bonos).
  - Calmar: CAGR / |Max Drawdown|.
  - Meses positivos/negativos: equity resampleado a fin de mes, % change,
    cuenta de signos.
  - Peor racha: máxima cantidad de operaciones perdedoras CONSECUTIVAS
    (por fecha de cierre), y cuánto capital se perdió en esa racha.
  - Monte Carlo: se reordena aleatoriamente la SECUENCIA de las
    operaciones ya ocurridas (2000 veces) y se recalcula el equity para
    cada orden -- esto mide riesgo de secuencia (¿importa el ORDEN en que
    vinieron las rachas?), NO robustez fuera de muestra (no genera
    operaciones nuevas, son las mismas 695-ish con distinto orden). Como
    acá el riesgo es en dólares FIJOS (no % del capital), el capital
    final es el MISMO en todos los reordenamientos -- lo que cambia es
    el drawdown máximo del camino. Se reporta la distribución del DD.
  - Correlación entre activos: retornos diarios de CIERRE a CIERRE del
    precio de cada uno de los 13 instrumentos (no del PnL de la
    estrategia), sobre el período que se solapan.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
import config
from portfolio_engine import INITIAL_CAPITAL, load, run_simulation
from run_live_trading import V1_LIVE_CONFIG

RNG_SEED = 42
MONTE_CARLO_ITERATIONS = 2000

DISPLAY_NAME = {
    "NCCOXAG2USD/USDT:USDT": "SILVER/USD", "NCSISP5002USD/USDT:USDT": "SP500/USD",
    "NCSINASDAQ1002USD/USDT:USDT": "NASDAQ100/USD", "NCCO1OILBRENT2USD/USDT:USDT": "OIL_BRENT/USD",
    "XAUT/USDT:USDT": "XAUT", "NCSKAMZN2USD/USDT:USDT": "AMZN/USD",
    "ADA/USDT:USDT": "ADA", "BNB/USDT:USDT": "BNB",
    "NCSKAAPL2USD/USDT:USDT": "AAPL/USD", "ETH/USDT:USDT": "ETH",
    "HYPE/USDT:USDT": "HYPE", "SOL/USDT:USDT": "SOL", "BTC/USDT:USDT": "BTC",
}


def compute_tearsheet(trades_df: pd.DataFrame, equity_df: pd.DataFrame) -> dict:
    if trades_df.empty:
        return {}

    capital_final = equity_df["capital"].iloc[-1]
    days = (equity_df["datetime"].iloc[-1] - equity_df["datetime"].iloc[0]).total_seconds() / 86400
    total_return_pct = (capital_final - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100
    cagr_pct = ((capital_final / INITIAL_CAPITAL) ** (365 / days) - 1) * 100 if days > 0 else 0

    wins = trades_df[trades_df["pnl_net"] > 0]
    losses = trades_df[trades_df["pnl_net"] <= 0]
    win_rate = len(wins) / len(trades_df) * 100
    gross_profit = wins["pnl_net"].sum()
    gross_loss = abs(losses["pnl_net"].sum())
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    # Equity diario (forward-fill entre cierres) para Sharpe/Sortino/meses
    eq = equity_df.set_index("datetime")["capital"]
    eq_daily = eq.resample("1D").last().ffill()
    daily_returns = eq_daily.pct_change().dropna()

    sharpe = (daily_returns.mean() / daily_returns.std()) * np.sqrt(365) if daily_returns.std() > 0 else np.nan
    downside = daily_returns[daily_returns < 0]
    sortino = (daily_returns.mean() / downside.std()) * np.sqrt(365) if len(downside) > 1 and downside.std() > 0 else np.nan

    running_max = eq_daily.cummax()
    dd_series = (eq_daily - running_max) / running_max * 100
    max_dd = dd_series.min()
    calmar = cagr_pct / abs(max_dd) if max_dd != 0 else np.nan

    eq_monthly = eq.resample("ME").last().ffill()
    monthly_returns = eq_monthly.pct_change().dropna()
    positive_months = int((monthly_returns > 0).sum())
    negative_months = int((monthly_returns <= 0).sum())

    trades_sorted = trades_df.sort_values("exit_datetime")
    is_loss = (trades_sorted["pnl_net"] <= 0).astype(int).values
    worst_streak = 0
    worst_streak_pnl = 0.0
    current_streak = 0
    current_streak_start = 0
    pnl_vals = trades_sorted["pnl_net"].values
    for i, loss in enumerate(is_loss):
        if loss:
            if current_streak == 0:
                current_streak_start = i
            current_streak += 1
            if current_streak > worst_streak:
                worst_streak = current_streak
                worst_streak_pnl = pnl_vals[current_streak_start:i + 1].sum()
        else:
            current_streak = 0

    # Monte Carlo: reordenar la secuencia de pnl_net ya ocurrida (riesgo fijo
    # en $ -> el capital final no cambia con el orden, solo el drawdown del camino)
    rng = np.random.default_rng(RNG_SEED)
    pnl_array = trades_df["pnl_net"].values
    mc_max_dds = []
    for _ in range(MONTE_CARLO_ITERATIONS):
        shuffled = rng.permutation(pnl_array)
        path = INITIAL_CAPITAL + np.cumsum(shuffled)
        running_max_mc = np.maximum.accumulate(np.concatenate([[INITIAL_CAPITAL], path]))
        dd_mc = (np.concatenate([[INITIAL_CAPITAL], path]) - running_max_mc) / running_max_mc * 100
        mc_max_dds.append(dd_mc.min())
    mc_max_dds = np.array(mc_max_dds)

    return {
        "capital_inicial": INITIAL_CAPITAL, "capital_final": capital_final, "dias": days,
        "retorno_pct": total_return_pct, "cagr_pct": cagr_pct, "profit_factor": profit_factor,
        "win_rate": win_rate, "sharpe": sharpe, "sortino": sortino, "max_dd_pct": max_dd,
        "calmar": calmar, "num_trades": len(trades_df), "trades_per_day": len(trades_df) / days if days > 0 else 0,
        "meses_positivos": positive_months, "meses_negativos": negative_months,
        "peor_racha_trades": worst_streak, "peor_racha_usd": worst_streak_pnl,
        "mc_dd_mediana": np.median(mc_max_dds), "mc_dd_p5": np.percentile(mc_max_dds, 5),
        "mc_dd_p95": np.percentile(mc_max_dds, 95), "mc_dd_peor": mc_max_dds.min(),
    }


def print_tearsheet(label: str, m: dict):
    print(f"\n{'=' * 70}\n{label}\n{'=' * 70}")
    print(f"Capital inicial:          ${m['capital_inicial']:.2f}")
    print(f"Capital final:            ${m['capital_final']:.2f}")
    print(f"Período analizado:        ~{m['dias']:.0f} días")
    print(f"Retorno total:            {m['retorno_pct']:.2f}%")
    print(f"CAGR:                     {m['cagr_pct']:.2f}%")
    print(f"Profit Factor:            {m['profit_factor']:.2f}")
    print(f"Sharpe (rf=0%, anual.):   {m['sharpe']:.2f}")
    print(f"Sortino (rf=0%, anual.):  {m['sortino']:.2f}")
    print(f"Max Drawdown:             {m['max_dd_pct']:.2f}%")
    print(f"Calmar:                   {m['calmar']:.2f}")
    print(f"Trades totales:           {m['num_trades']}  ({m['trades_per_day']:.2f}/día)")
    print(f"Meses positivos/negativos:{m['meses_positivos']} / {m['meses_negativos']}")
    print(f"Peor racha:               {m['peor_racha_trades']} operaciones perdedoras seguidas (${m['peor_racha_usd']:.2f})")
    print(f"Monte Carlo DD (2000 sim.), mediana / p5 / p95 / peor caso:")
    print(f"  {m['mc_dd_mediana']:.2f}% / {m['mc_dd_p5']:.2f}% / {m['mc_dd_p95']:.2f}% / {m['mc_dd_peor']:.2f}%")


def compute_correlation_matrix(live_config: dict) -> pd.DataFrame:
    series = {}
    for symbol in live_config:
        fname = symbol.replace("/", "_").replace(":", "_")
        path = os.path.join(config.DATA_DIR, f"{fname}_15m.csv")
        if not os.path.exists(path):
            continue
        df_entry, _ = load(symbol)
        daily_close = df_entry.set_index("datetime")["close"].resample("1D").last().dropna()
        daily_return = daily_close.pct_change().dropna()
        series[DISPLAY_NAME.get(symbol, symbol)] = daily_return

    df = pd.DataFrame(series)
    return df.corr()


def main():
    os.makedirs(config.RESULTS_DIR, exist_ok=True)
    data_cache = {}

    print("Corriendo simulación con la config REAL (R:R calibrado por símbolo, hoy 1:2.0 todos)...")
    trades_real, equity_real = run_simulation(V1_LIVE_CONFIG, tp_rr_override=None, data_cache=data_cache)
    m_real = compute_tearsheet(trades_real, equity_real)
    print_tearsheet("CONFIG REAL (R:R por símbolo, ~1:2.0)", m_real)

    print("\n\nCorriendo simulación con TODOS los símbolos forzados a 1:2.3...")
    trades_23, equity_23 = run_simulation(V1_LIVE_CONFIG, tp_rr_override=2.3, data_cache=data_cache)
    m_23 = compute_tearsheet(trades_23, equity_23)
    print_tearsheet("TODOS LOS SÍMBOLOS A 1:2.3", m_23)

    print("\n\nCalculando correlación de retornos diarios entre los 13 activos...")
    corr = compute_correlation_matrix(V1_LIVE_CONFIG)
    corr.to_csv(os.path.join(config.RESULTS_DIR, "portfolio_correlation_matrix.csv"))
    print(corr.round(2).to_string())

    pd.DataFrame([
        {"config": "real_1_2.0", **m_real},
        {"config": "forzado_1_2.3", **m_23},
    ]).to_csv(os.path.join(config.RESULTS_DIR, "portfolio_tearsheet_comparison.csv"), index=False)
    print("\nGuardado en results/portfolio_tearsheet_comparison.csv y results/portfolio_correlation_matrix.csv")


if __name__ == "__main__":
    main()
