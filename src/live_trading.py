"""
Ejecución de órdenes REALES en BingX para el bot scalper. Misma cuenta/API
key que fibo-reversal-bot (confirmado por el usuario), pero el capital que
usa este bot para el sizing de posiciones está TOPEADO en
config.MAX_CAPITAL_USDT (no usa todo el balance libre de la cuenta), para
no competir por capital si el bot Fibo se reactiva más adelante.

Salvaguardas (mismo criterio que fibo-reversal-bot/src/live_trading.py):
  - Interruptor de emergencia: STOP_TRADING.flag en la raíz del proyecto.
  - Tope duro de riesgo por operación en USD (MAX_RISK_USDT_PER_TRADE).
  - Valida contra el mínimo de notional/cantidad del símbolo en BingX.
  - Stop Loss y Take Profit ADJUNTOS a la orden de entrada (protegidos del
    lado del exchange, sobreviven si esta PC se apaga).
  - Todo se loguea en logs/live_trading_log.txt.
"""
import json
import os
import sys
import time
from datetime import datetime, timezone

import ccxt
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KILL_SWITCH_PATH = os.path.join(PROJECT_ROOT, "STOP_TRADING.flag")
LIVE_STATE_DIR = os.path.join(config.RESULTS_DIR, "live_trading")
LIVE_STATE_PATH = os.path.join(LIVE_STATE_DIR, "state.json")
LIVE_LOG_PATH = os.path.join(PROJECT_ROOT, "logs", "live_trading_log.txt")

MAX_RISK_USDT_PER_TRADE = 5.0  # tope duro en USD, aunque el % calculado dé más

# Prefijo para taggear las órdenes propias del scalper (clientOrderId). La
# cuenta es compartida con fibo-reversal-bot -- BingX no permite "taggear"
# posiciones abiertas (solo órdenes), así que la reconciliación de
# seguridad se hace sobre ÓRDENES propias identificadas por este prefijo,
# no sobre el total de posiciones de la cuenta (eso incluiría lo de Fibo).
CLIENT_ORDER_PREFIX = "scalperv1"


def log(msg: str):
    os.makedirs(os.path.dirname(LIVE_LOG_PATH), exist_ok=True)
    line = f"[{datetime.now(timezone.utc).isoformat()}] {msg}"
    try:
        print(line)
    except UnicodeEncodeError:
        # La consola de Windows (cp1252) no puede encodear ciertos caracteres
        # -- ej. el mensaje en chino de un error de BingX (100410). Antes esto
        # tumbaba el ciclo entero desde el except que intentaba loguear el
        # error original. El archivo se escribe igual en utf-8 más abajo.
        enc = getattr(sys.stdout, "encoding", None) or "utf-8"
        print(line.encode(enc, errors="replace").decode(enc, errors="replace"))
    for attempt in range(3):
        try:
            with open(LIVE_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(line + "\n")
            return
        except PermissionError:
            if attempt == 2:
                return
            time.sleep(0.5)


def kill_switch_active() -> bool:
    return os.path.exists(KILL_SWITCH_PATH)


def get_exchange():
    load_dotenv()
    api_key = os.getenv("BINGX_API_KEY")
    api_secret = os.getenv("BINGX_API_SECRET")
    if not api_key or not api_secret:
        raise RuntimeError("Faltan BINGX_API_KEY / BINGX_API_SECRET en el .env")

    exchange = ccxt.bingx({
        "apiKey": api_key, "secret": api_secret,
        "enableRateLimit": True, "timeout": 30000,
        "options": {"defaultType": config.MARKET_TYPE},
    })
    exchange.load_markets()
    return exchange


def ensure_leverage(exchange, symbols, leverage=config.LEVERAGE):
    """
    `leverage` puede ser un número (mismo apalancamiento para todos los
    symbols) o un dict {symbol: leverage} -- necesario porque V1 usa 15x
    y V5 usa 50x sobre símbolos distintos en el mismo bot.
    """
    for symbol in symbols:
        lev = leverage[symbol] if isinstance(leverage, dict) else leverage
        for side in ["LONG", "SHORT"]:
            try:
                exchange.set_leverage(lev, symbol, params={"side": side})
                log(f"Apalancamiento {lev}x confirmado para {symbol} ({side})")
            except Exception as e:
                log(f"[!] No se pudo fijar apalancamiento para {symbol} ({side}): {e}")


def _load_state() -> dict:
    if os.path.exists(LIVE_STATE_PATH):
        with open(LIVE_STATE_PATH, "r") as f:
            return json.load(f)
    return {"last_processed_signal": {}, "open_orders": []}


def _save_state(state: dict):
    os.makedirs(LIVE_STATE_DIR, exist_ok=True)
    with open(LIVE_STATE_PATH, "w") as f:
        json.dump(state, f, indent=2, default=str)


def compute_valid_position_size(exchange, symbol, risk_base_capital, risk_pct, entry_price, stop_price, leverage,
                                 available_capital=None):
    """
    risk_base_capital: base sobre la que se calcula el 2% de riesgo -- con
    piso en config.MAX_CAPITAL_USDT (nunca arriesga menos que eso aunque el
    balance real esté más bajo), pero SIN techo (si el balance real supera
    ese piso, el riesgo crece con él). Confirmado por el usuario 2026-08-04.
    available_capital: balance real disponible -- se usa SOLO para
    verificar que el margen requerido efectivamente se pueda cubrir (si es
    None, se asume igual a risk_base_capital, comportamiento anterior).
    """
    if available_capital is None:
        available_capital = risk_base_capital

    risk_amount = min(risk_base_capital * risk_pct, MAX_RISK_USDT_PER_TRADE)
    stop_distance = abs(entry_price - stop_price)
    if stop_distance <= 0:
        return None

    position_size = risk_amount / stop_distance
    notional = position_size * entry_price
    margin_required = notional / leverage

    market = exchange.markets[symbol]
    min_amount = market["limits"]["amount"]["min"] or 0
    min_cost = market["limits"]["cost"]["min"] or 0

    if position_size < min_amount or notional < min_cost:
        log(f"  [salteada] {symbol}: tamaño calculado ({position_size:.6f}, ${notional:.2f}) "
            f"no alcanza el mínimo del exchange (min_amount={min_amount}, min_cost=${min_cost})")
        return None

    if margin_required > available_capital:
        log(f"  [salteada] {symbol}: margen requerido (${margin_required:.2f}) supera el capital REAL "
            f"disponible (${available_capital:.2f}) -- el riesgo se calculó sobre ${risk_base_capital:.2f} "
            f"(piso ${config.MAX_CAPITAL_USDT:.2f}), pero la cuenta no tiene margen suficiente para cubrirlo.")
        return None

    position_size = exchange.amount_to_precision(symbol, position_size)
    return float(position_size), risk_amount


def fetch_own_open_orders(exchange):
    """Órdenes abiertas que pertenecen a ESTE bot (clientOrderId con el
    prefijo propio) -- filtra las de fibo-reversal-bot en la misma cuenta."""
    all_orders = exchange.fetch_open_orders()
    return [o for o in all_orders if (o.get("clientOrderId") or "").startswith(CLIENT_ORDER_PREFIX)]


def fetch_open_position_symbols(exchange, symbols):
    """Símbolos de la lista dada que tienen una posición realmente abierta en
    el exchange (contracts != 0). fetch_own_open_orders() sólo ve órdenes
    PENDIENTES: en cuanto la entrada se llena (orden market, o limit que
    toca precio), desaparece de ahí aunque la posición siga abierta con su
    SL/TP puestos -- eso permitía que el bot re-entrara sobre el mismo activo
    en la misma zona. BingX no permite taggear posiciones por bot (sólo
    órdenes), así que esto no distingue si la posición es de este bot o de
    fibo-reversal-bot -- pero para el objetivo de "no apilar entradas en el
    mismo activo" cualquier posición abierta en ese símbolo debe bloquear
    una entrada nueva."""
    positions = exchange.fetch_positions(symbols)
    return {p["symbol"] for p in positions if (p.get("contracts") or 0) != 0}


def place_entry_with_sl_tp(exchange, setup, position_size):
    """Coloca la orden de entrada (límite o mercado) con SL/TP adjuntos."""
    # Validación previa contra el precio actual: el stop se calcula sobre la
    # vela de la señal (puede tener minutos de antigüedad), y si el precio se
    # movió lo suficiente desde entonces, el SL puede quedar del lado
    # incorrecto del precio en vivo -- BingX lo rechaza con "SL Price must be
    # greater/less than Last Price" (visto en vivo con NCCOXAG2USD el
    # 2026-08-26). Se chequea ACA para loguear un skip claro en vez de gastar
    # una llamada a create_order que el exchange va a rechazar igual.
    last_price = exchange.fetch_ticker(setup.symbol)["last"]
    if setup.direction == "short" and setup.stop_price <= last_price:
        log(f"  [salteada] {setup.symbol} {setup.strategy}: señal obsoleta -- el SL calculado "
            f"({setup.stop_price:.4f}) ya no queda por encima del precio actual (${last_price:.4f}).")
        return None
    if setup.direction == "long" and setup.stop_price >= last_price:
        log(f"  [salteada] {setup.symbol} {setup.strategy}: señal obsoleta -- el SL calculado "
            f"({setup.stop_price:.4f}) ya no queda por debajo del precio actual (${last_price:.4f}).")
        return None

    side = "buy" if setup.direction == "long" else "sell"
    order_type = "limit" if setup.is_limit else "market"
    price = setup.entry_price_target if setup.is_limit else None

    position_side = "LONG" if setup.direction == "long" else "SHORT"
    client_order_id = f"{CLIENT_ORDER_PREFIX}{int(time.time() * 1000)}"
    params = {
        "positionSide": position_side,
        "clientOrderId": client_order_id,
        "stopLoss": {"triggerPrice": exchange.price_to_precision(setup.symbol, setup.stop_price)},
        "takeProfit": {"triggerPrice": exchange.price_to_precision(setup.symbol, setup.take_profit_price)},
    }

    dry_run = os.getenv("LIVE_TRADING_DRY_RUN", "false").lower() == "true"
    if dry_run:
        params["test"] = True

    order = exchange.create_order(setup.symbol, order_type, side, position_size, price, params=params)
    tag = "[DRY-RUN, no ejecutada de verdad]" if dry_run else "[ORDEN REAL ENVIADA]"
    log(f"  {tag} {setup.symbol} {setup.strategy} {side} {order_type} "
        f"size={position_size} entry~={setup.entry_price_target:.4f} "
        f"SL={setup.stop_price:.4f} TP={setup.take_profit_price:.4f} -> orderId={order.get('id')}")
    return order
