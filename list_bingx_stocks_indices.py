"""
Búsqueda puntual (no el catálogo completo) de RUSSELL2000, GOOGL, META y
NVDA entre los CFDs sintéticos de BingX (prefijos NCSK=acciones,
NCSI=índices). Salida corta a propósito -- solo lo que matchea.

Uso:
    python list_bingx_stocks_indices.py
"""
import ccxt

KEYWORDS = ["GOOGL", "GOOG", "META", "NVDA", "RUSSELL", "RUT", "RUSS", "US2000", "R2K", "2000"]

exchange = ccxt.bingx({"options": {"defaultType": "swap"}})
exchange.load_markets()

nc_symbols = [s for s in exchange.symbols if s.startswith("NCSK") or s.startswith("NCSI")]
matches = sorted(s for s in nc_symbols if any(k in s.upper() for k in KEYWORDS))

print(f"Total de símbolos NCSK/NCSI en BingX: {len(nc_symbols)}")
print(f"Coincidencias para {KEYWORDS}: {len(matches)}\n")

if not matches:
    print("Ninguno de los 4 aparece con estos nombres.")
else:
    for s in matches:
        m = exchange.markets[s]
        try:
            candles = exchange.fetch_ohlcv(s, timeframe="1h", limit=2)
            estado = f"OK ({len(candles)} velas)" if candles else "sin velas"
        except Exception as e:
            estado = f"ERROR: {e}"
        print(f"  {s}  (id={m.get('id')}, active={m.get('active')}) -- histórico: {estado}")
