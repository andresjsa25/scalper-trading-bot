"""
Simulador de portafolio COMBINADO: los 13 activos de V1_LIVE_CONFIG
corriendo juntos con UN SOLO capital compartido -- a diferencia de los
backtests anteriores (cada símbolo aislado con $1000 propios), esto
respeta los mismos topes que el bot real en vivo (MAX_CONCURRENT_TRADES,
máximo 1 operación por símbolo a la vez).

Importa V1_LIVE_CONFIG directo de run_live_trading.py -- una sola fuente
de verdad, si se recalibra un símbolo ahí, este simulador lo usa
automáticamente sin tener que duplicar números acá.

CAMBIO 2026-08-08 -- riesgo en dólares fijos, no en % del capital
corriente: la primera versión usaba risk_amount = capital_actual * 2%
(igual que el motor de un solo símbolo), y con ~700 operaciones seguidas
sobre un solo pool eso compone cientos de veces y da un retorno
absurdo (+11614% anualizado) -- no por un bug, sino porque nada topaba
el tamaño de posición a medida que el capital crecía sin límite (ni
siquiera el bot real lo hace: su fórmula documentada en config.py es
"sin techo"). Acá el riesgo es fijo: config.MAX_CAPITAL_USDT * risk_pct,
constante en cada operación sin importar cuánto creció o cayó el
capital -- más estricto que el propio diseño del bot real, a propósito,
para tener un número de retorno creíble en vez de uno inflado por
interés compuesto. El capital inicial también se alinea a
config.MAX_CAPITAL_USDT (la escala real en la que opera la cuenta hoy),
no al $1000 de conveniencia de los backtests aislados.

Reusa exactamente la misma matemática de costos (fees, slippage, buffer
de liquidación) que backtest.py, pero como una cola de eventos
cronológica (apertura/cierre) en vez de barra por barra -- son ~700
operaciones en ~250-590 días según el símbolo, así que es mucho más
rápido sin perder precisión: cuando se abre una posición, se escanea
hacia adelante en el propio historial de ESE símbolo para saber cuándo
y a qué precio se resuelve (SL/TP/time_exit) -- eso es independiente de
los demás símbolos. Lo único que depende de los demás activos es CUÁNTO
riesgo/margen hay disponible en el momento de abrir.

NO modela (limitación conocida, igual que backtest.py): funding rate de
los perpetuos, mínimos de notional/cantidad del exchange.
"""
import os
import sys
from dataclasses import dataclass

import pandas as pd

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
import config
from strategy_v1_sniper import generate_setups
from entry_filters import apply_entry_filter
from backtest import MAINTENANCE_MARGIN_RATE_ESTIMATE
from run_live_trading import V1_LIVE_CONFIG

# Mismo capital de referencia que usa el bot real (config.MAX_CAPITAL_USDT),
# no el $1000 de conveniencia de los backtests aislados por símbolo -- así
# el tamaño de cuenta es consistente con el riesgo fijo en dólares de arriba.
INITIAL_CAPITAL = config.MAX_CAPITAL_USDT

DISPLAY_NAME = {
    "NCCOXAG2USD/USDT:USDT": "SILVER/USD", "NCSISP5002USD/USDT:USDT": "SP500/USD",
    "NCSINASDAQ1002USD/USDT:USDT": "NASDAQ100/USD", "NCCO1OILBRENT2USD/USDT:USDT": "OIL_BRENT/USD",
    "XAUT/USDT:USDT": "XAUT", "NCSKAMZN2USD/USDT:USDT": "AMZN/USD",
    "ADA/USDT:USDT": "ADA", "BNB/USDT:USDT": "BNB",
    "NCSKAAPL2USD/USDT:USDT": "AAPL/USD", "ETH/USDT:USDT": "ETH",
    "HYPE/USDT:USDT": "HYPE", "SOL/USDT:USDT": "SOL", "BTC/USDT:USDT": "BTC",
}


def load(symbol):
    fname = symbol.replace("/", "_").replace(":", "_")
    df_entry = pd.read_csv(os.path.join(config.DATA_DIR, f"{fname}_15m.csv"))
    df_context = pd.read_csv(os.path.join(config.DATA_DIR, f"{fname}_1h.csv"))
    df_entry["datetime"] = pd.to_datetime(df_entry["datetime"], utc=True)
    df_context["datetime"] = pd.to_datetime(df_context["datetime"], utc=True)
    return df_entry, df_context


def find_exit(df_entry, setup):
    """Misma lógica de resolución que backtest.simulate_trades, extraída para reusar acá."""
    df_slice = df_entry.iloc[setup.signal_bar_pos + 1: setup.valid_until_pos + 1]
    for _, bar in df_slice.iterrows():
        if setup.direction == "long":
            hit_sl = bar["low"] <= setup.stop_price
            hit_tp = bar["high"] >= setup.take_profit_price
        else:
            hit_sl = bar["high"] >= setup.stop_price
            hit_tp = bar["low"] <= setup.take_profit_price
        if hit_sl:
            return setup.stop_price, bar["datetime"], "stop_loss"
        if hit_tp:
            return setup.take_profit_price, bar["datetime"], "take_profit"
    if len(df_slice) == 0:
        return None, None, None
    last_bar = df_slice.iloc[-1]
    return last_bar["close"], last_bar["datetime"], "time_exit"


@dataclass
class OpenPosition:
    symbol: str
    strategy: str
    direction: str
    entry_price: float
    position_size: float
    notional: float
    risk_amount: float
    is_limit: bool
    entry_datetime: pd.Timestamp
    exit_price: float
    exit_datetime: pd.Timestamp
    exit_reason: str


def main():
    print("Cargando datos y generando setups de los 13 activos (config real de V1_LIVE_CONFIG)...")
    all_setups = []
    data_by_symbol = {}

    for symbol, cfg in V1_LIVE_CONFIG.items():
        fname = symbol.replace("/", "_").replace(":", "_")
        path = os.path.join(config.DATA_DIR, f"{fname}_15m.csv")
        if not os.path.exists(path):
            print(f"[!] Sin datos para {symbol}, se salta")
            continue

        df_entry, df_context = load(symbol)
        data_by_symbol[symbol] = df_entry

        config.TP_RR_RATIO = cfg["tp_rr_ratio"]
        setups = generate_setups(
            symbol, df_context, df_entry,
            min_swing_percentile=cfg["percentile"], use_trend_filter=cfg["use_trend_filter"],
            use_session_filter=cfg["use_session_filter"], require_regime=cfg["require_regime"],
        )
        setups = apply_entry_filter(setups, df_entry, cfg["ema_filter"])
        all_setups.extend(setups)

    all_setups.sort(key=lambda s: s.signal_datetime)
    span_days = (all_setups[-1].signal_datetime - all_setups[0].signal_datetime).total_seconds() / 86400
    print(f"Total de setups candidatos (13 activos, orden cronológico): {len(all_setups)} en ~{span_days:.0f} días")

    capital = INITIAL_CAPITAL
    open_risk = 0.0
    open_by_symbol = set()
    pending_closes = []  # [(exit_datetime, OpenPosition), ...]
    closed_trades = []
    equity_curve = [capital]
    skipped_portfolio_cap = 0
    skipped_concurrent_cap = 0
    skipped_same_symbol = 0

    def close_due(up_to_datetime):
        nonlocal capital, open_risk
        pending_closes.sort(key=lambda x: x[0])
        while pending_closes and pending_closes[0][0] <= up_to_datetime:
            _, pos = pending_closes.pop(0)
            open_by_symbol.discard(pos.symbol)

            entry_fee_rate = config.MAKER_FEE_PCT if pos.is_limit else config.TAKER_FEE_PCT
            exit_fee_rate = config.TAKER_FEE_PCT
            entry_slip = pos.entry_price * config.SLIPPAGE_PCT_ESTIMATE
            exit_slip = pos.exit_price * config.SLIPPAGE_PCT_ESTIMATE
            if pos.direction == "long":
                eff_entry = pos.entry_price + entry_slip
                eff_exit = pos.exit_price - exit_slip
                pnl_gross = (eff_exit - eff_entry) * pos.position_size
            else:
                eff_entry = pos.entry_price - entry_slip
                eff_exit = pos.exit_price + exit_slip
                pnl_gross = (eff_entry - eff_exit) * pos.position_size

            entry_fee = pos.notional * entry_fee_rate
            exit_fee = (pos.position_size * pos.exit_price) * exit_fee_rate
            pnl_net = pnl_gross - entry_fee - exit_fee

            capital += pnl_net
            open_risk -= pos.risk_amount
            closed_trades.append({
                "symbol": pos.symbol, "strategy": pos.strategy, "direction": pos.direction,
                "entry_datetime": pos.entry_datetime, "exit_datetime": pos.exit_datetime,
                "exit_reason": pos.exit_reason, "pnl_net": pnl_net,
                "r_multiple": pnl_net / pos.risk_amount if pos.risk_amount else 0,
                "capital_after": capital,
            })
            equity_curve.append(capital)

    for setup in all_setups:
        if capital <= 0:
            print("[!] Capital agotado -- se detiene la simulación acá.")
            break

        close_due(setup.signal_datetime)

        if setup.symbol in open_by_symbol:
            skipped_same_symbol += 1
            continue
        if len(pending_closes) >= config.MAX_CONCURRENT_TRADES:
            skipped_concurrent_cap += 1
            continue

        entry_price = setup.entry_price_target
        stop_price = setup.stop_price
        stop_distance_pct = abs(entry_price - stop_price) / entry_price
        liq_buffer = (1 / config.LEVERAGE) - MAINTENANCE_MARGIN_RATE_ESTIMATE
        if stop_distance_pct >= liq_buffer:
            continue

        # Riesgo en DÓLARES FIJOS (config.MAX_CAPITAL_USDT * risk_pct), no un
        # % del capital corriente -- así el tamaño de cada operación no
        # compone con las ganancias previas. Es más estricto que el propio
        # bot real (que en su diseño documentado no tiene techo: el riesgo
        # crece sin límite si el balance real crece), a propósito, para
        # tener un número de retorno creíble en vez de uno inflado por
        # interés compuesto sobre cientos de operaciones seguidas.
        risk_amount = config.MAX_CAPITAL_USDT * setup.risk_pct
        if (open_risk + risk_amount) / config.MAX_CAPITAL_USDT > config.MAX_PORTFOLIO_RISK_PCT:
            skipped_portfolio_cap += 1
            continue

        position_size = risk_amount / abs(entry_price - stop_price)
        notional = position_size * entry_price
        margin_required = notional / config.LEVERAGE
        if margin_required > capital:
            position_size = (capital * config.LEVERAGE) / entry_price
            notional = position_size * entry_price

        df_entry = data_by_symbol[setup.symbol]
        exit_price, exit_dt, exit_reason = find_exit(df_entry, setup)
        if exit_price is None:
            continue

        pos = OpenPosition(
            symbol=setup.symbol, strategy=setup.strategy, direction=setup.direction,
            entry_price=entry_price, position_size=position_size, notional=notional,
            risk_amount=risk_amount, is_limit=setup.is_limit, entry_datetime=setup.signal_datetime,
            exit_price=exit_price, exit_datetime=exit_dt, exit_reason=exit_reason,
        )
        open_by_symbol.add(setup.symbol)
        open_risk += risk_amount
        pending_closes.append((exit_dt, pos))

    close_due(pd.Timestamp.max.tz_localize("UTC"))

    df = pd.DataFrame(closed_trades)
    df.to_csv(os.path.join(config.RESULTS_DIR, "portfolio_simulation_trades.csv"), index=False)

    wins = df[df["pnl_net"] > 0]
    losses = df[df["pnl_net"] <= 0]
    win_rate = len(wins) / len(df) * 100 if len(df) else 0
    gross_profit = wins["pnl_net"].sum()
    gross_loss = abs(losses["pnl_net"].sum())
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    equity_series = pd.Series(equity_curve)
    running_max = equity_series.cummax()
    drawdown = (equity_series - running_max) / running_max * 100
    max_dd = drawdown.min()

    total_return_pct = (capital - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100
    annualized_return_pct = total_return_pct * (365 / span_days) if span_days > 0 else 0
    trades_per_day = len(df) / span_days if span_days > 0 else 0

    print("\n" + "=" * 70)
    print("RESULTADO DEL PORTAFOLIO COMBINADO (13 activos, capital compartido)")
    print("=" * 70)
    print(f"Capital inicial: ${INITIAL_CAPITAL:.2f}")
    print(f"Capital final:   ${capital:.2f}")
    print(f"Operaciones ejecutadas: {len(df)}  |  {trades_per_day:.2f} trades/día combinados")
    print(f"Win rate: {win_rate:.1f}%  |  Profit Factor: {profit_factor:.2f}")
    print(f"Retorno del período (~{span_days:.0f} días): {total_return_pct:.2f}%")
    print(f"Retorno anualizado (lineal a 365 días): {annualized_return_pct:.2f}%")
    print(f"Máximo drawdown del portafolio: {max_dd:.2f}%")
    print(f"\nSetups descartados por tope de portafolio (30% riesgo abierto): {skipped_portfolio_cap}")
    print(f"Setups descartados por tope de operaciones simultáneas (10): {skipped_concurrent_cap}")
    print(f"Setups descartados por ya tener una operación abierta en el mismo símbolo: {skipped_same_symbol}")

    print("\nDesglose por símbolo (operaciones ejecutadas en la simulación combinada):")
    by_symbol = df.groupby("symbol").agg(
        trades=("pnl_net", "count"),
        win_rate=("pnl_net", lambda x: (x > 0).mean() * 100),
        pnl_total=("pnl_net", "sum"),
    )
    by_symbol["display_name"] = [DISPLAY_NAME.get(s, s) for s in by_symbol.index]
    print(by_symbol[["display_name", "trades", "win_rate", "pnl_total"]].to_string(index=False))

    print(f"\nGuardado en results/portfolio_simulation_trades.csv")


if __name__ == "__main__":
    main()
