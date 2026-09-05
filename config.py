"""
Configuración central del bot scalper de liquidez (15min/1h).
Gestión de riesgo, exchange, comisiones y slippage: MISMOS valores que
fibo-reversal-bot/config.py (bot ya activo), por pedido explícito del
usuario -- no se inventa nada nuevo acá, se reusa lo ya validado.
El TP_RR_RATIO arranca en 1:1 (según lo pedido, siguiendo la lógica del
video de SANCHEZZFX) y se irá ajustando según lo que diga el backtesting.
"""

# --- Mercado ---
EXCHANGE_ID = "bingx"
MARKET_TYPE = "swap"

# Mismos 10 activos que fibo-reversal-bot (ya con histórico descargado y
# verificado -- ver fibo-reversal-bot/config.py y calibrate_and_backtest_indices.py)
SYMBOLS = [
    "BTC/USDT:USDT", "ETH/USDT:USDT", "XAUT/USDT:USDT",
    "NCSISP5002USD/USDT:USDT",      # SP500/USD
    # "NCSINASDAQ1002USD/USDT:USDT", # NASDAQ100/USD -- sacado (sep 2026):
    # backtest de V1 (config ya probada) dio PF 0.98 en 100 días reales, y el
    # walk-forward out-of-sample (45/15 días, ver run_walkforward_stocks_test.py)
    # confirmó PF 0.71 / retorno -7.65% -- no se sostiene, mismo criterio que
    # AMZN antes. Ver results/backtest_3strategies_comparison.csv y
    # results/stocks_test_walkforward_summary_combined.csv.
    "NCCO1OILBRENT2USD/USDT:USDT",  # OIL_BRENT/USD
    "NCCOXAG2USD/USDT:USDT",        # SILVER/USD
    "HYPE/USDT:USDT",               # HYPE/USD (cripto real)
    "NCSKAAPL2USD/USDT:USDT",       # AAPL/USD
    "NCSKGOOGL2USD/USDT:USDT",      # GOOGL/USD -- sumado sep 2026 (V1 y V5,
    # ver V1_LIVE_CONFIG/V5_LIVE_CONFIG en run_live_trading.py)
    "NCSKMETA2USD/USDT:USDT",       # META/USD -- sumado sep 2026 (V1)
    "NCSKNVDA2USD/USDT:USDT",       # NVDA/USD -- sumado sep 2026 (V1)
    # "NCSKAMZN2USD/USDT:USDT",     # AMZN/USD -- sacado (sep 2026): 3-4
    # pérdidas seguidas en vivo. Se reemplaza por EUR/USD y USD/JPY, una vez
    # que el backtesting con datos de Dukascopy (fetch_data_forex.py) diga
    # con qué estrategia/config conviene sumarlos.
]

TIMEFRAME_ENTRY = "15m"    # estructura + patrón de entrada (M15/M5 en los videos)
TIMEFRAME_CONTEXT = "1h"   # liquidez / sesgo direccional (H4/diario en los videos)

HISTORY_YEARS = 1.5  # igual que fibo-reversal-bot; cada símbolo se recorta a lo que tenga real

# --- Gestión de riesgo (idéntica a fibo-reversal-bot) ---
RISK_PER_TRADE_PCT = 0.02
LEVERAGE = 15
INITIAL_CAPITAL_USDT = 1000.0  # capital de referencia para el backtest ($1000 aislado por símbolo)

# --- Trading en vivo ---
# Misma cuenta/API key que fibo-reversal-bot (confirmado por el usuario,
# 2026-08-04). Originalmente este valor operaba como TOPE de capital para
# no competir con fibo-reversal-bot por el balance de la cuenta compartida.
# Desde 2026-08-25, a pedido del usuario, run_live_trading.py ya NO usa
# este valor para el sizing -- arriesga siempre sobre el balance real de
# la cuenta (sube o baja con él, sin piso ni techo). Si fibo-reversal-bot
# se reactiva y comparte la misma cuenta, este bot va a competir por el
# 100% del balance libre -- avisar si eso vuelve a ser un problema.
MAX_CAPITAL_USDT = 300.0  # ya no se usa en el sizing en vivo -- ver run_live_trading.py
MAX_PORTFOLIO_RISK_PCT = 0.30   # mismo tope que fibo-reversal-bot
MAX_CONCURRENT_TRADES = 10      # mismo tope que fibo-reversal-bot
TP_RR_RATIO = 2.0  # 1:1 dio PF<1 en la mayoría de activos: con stops ajustados
# (~0.5%) las comisiones se comen ~13% de cada R, empujando el breakeven muy
# por encima de 50% de win rate. Se pasa a 1:2 (nativo del video1) para
# diluir ese peso -- confirmado por el usuario el 2026-08-02.

# --- Costos de operar (idénticos a fibo-reversal-bot, misma fee schedule BingX) ---
MAKER_FEE_PCT = 0.0002
TAKER_FEE_PCT = 0.0005
SLIPPAGE_PCT_ESTIMATE = 0.0002

# --- Filtro de horario de sesión (UTC) ---
# Los 3 videos coinciden en operar solo en aperturas de Londres y Nueva York
# (mayor volumen/volatilidad -> movimientos limpios). Horarios en UTC:
#   Londres abre  8:00 UTC  -> ventana operativa 8:00-10:00 UTC
#   Nueva York abre 13:30 UTC -> ventana operativa 13:30-16:00 UTC
# (Nota: durante el horario de verano europeo/americano estos rangos se
# mantienen en UTC fijo; no se ajusta por DST, igual que asumen los videos
# al hablar en hora local sin más detalle.)
SESSION_WINDOWS_UTC = [
    ("08:00", "10:00"),  # Londres
    ("13:30", "16:00"),  # Nueva York
]

# --- Patrones de vela (V5, mismos umbrales validados en fibo-reversal-bot) ---
TWEEZER_HL_TOLERANCE_PCT = 0.001
HAMMER_WICK_TO_BODY_RATIO = 2.0
HAMMER_OPPOSITE_WICK_MAX_RATIO = 0.25

# --- Rutas ---
DATA_DIR = "data"
RESULTS_DIR = "results"
