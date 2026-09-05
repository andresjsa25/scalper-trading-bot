"""
Diagnóstico: lista todos los mercados de BingX que contengan EUR o JPY en
el símbolo, en los tipos de mercado disponibles (spot, swap USDT-M,
margin), para encontrar el nombre exacto que usa la API de EUR/USD y
USD/JPY -- el usuario los opera manual en la app de BingX, así que existen,
solo hay que encontrar cómo los ve ccxt/la API pública.

Uso:
    python list_bingx_forex_markets.py
"""
import ccxt

for market_type in ["spot", "swap", "margin"]:
    print(f"\n=== defaultType={market_type} ===")
    try:
        exchange = ccxt.bingx({"options": {"defaultType": market_type}})
        exchange.load_markets()
        matches = [s for s in exchange.symbols if "EUR" in s.upper() or "JPY" in s.upper()]
        if not matches:
            print("  (sin coincidencias)")
        for s in sorted(matches):
            m = exchange.markets[s]
            print(f"  {s}  (id={m.get('id')}, active={m.get('active')}, type={m.get('type')})")
    except Exception as e:
        print(f"  [!] Error con defaultType={market_type}: {e}")

print("\n=== Prueba de fetch_ohlcv (5 velas recientes) sobre cada coincidencia ===")
for market_type in ["spot", "swap", "margin"]:
    try:
        exchange = ccxt.bingx({"options": {"defaultType": market_type}})
        exchange.load_markets()
        matches = [s for s in exchange.symbols if "EUR" in s.upper() or "JPY" in s.upper()]
        for s in matches:
            try:
                candles = exchange.fetch_ohlcv(s, timeframe="1h", limit=5)
                print(f"  [{market_type}] {s}: {len(candles)} velas -- ejemplo: {candles[-1] if candles else None}")
            except Exception as e:
                print(f"  [{market_type}] {s}: ERROR al pedir OHLCV -- {e}")
    except Exception:
        continue
