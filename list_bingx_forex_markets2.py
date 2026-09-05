"""
Segunda pasada del diagnóstico: la app de BingX muestra los tickers como
"EURUSD/USDT Perp" y "USDJPY/USDT Perp" (un solo ticker compuesto contra
USDT, no "EUR/USD" como dos monedas separadas) -- eso no apareció en la
primera búsqueda por texto "EUR"/"JPY" en el símbolo unificado de ccxt,
así que puede estar bajo otro market type, o con un id que ccxt no mapeó
al symbol unificado esperado. Acá se prueba directo con el símbolo/id que
muestra la app, y se revisa el id crudo de cada mercado (no solo el
symbol unificado) por si el filtro de antes lo pasó por alto.
"""
import ccxt

CANDIDATES = ["EURUSD/USDT:USDT", "USDJPY/USDT:USDT", "EURUSD/USDT", "USDJPY/USDT"]

for market_type in ["swap", "spot"]:
    print(f"\n=== defaultType={market_type} -- buscando por id crudo ===")
    exchange = ccxt.bingx({"options": {"defaultType": market_type}})
    exchange.load_markets()
    id_matches = [s for s, m in exchange.markets.items()
                  if "EURUSD" in (m.get("id") or "").upper() or "USDJPY" in (m.get("id") or "").upper()]
    if not id_matches:
        print("  (sin coincidencias por id)")
    for s in id_matches:
        m = exchange.markets[s]
        print(f"  symbol={s}  id={m.get('id')}  active={m.get('active')}  type={m.get('type')}")

    print(f"  Probando símbolos literales de la app en defaultType={market_type}...")
    for cand in CANDIDATES:
        try:
            candles = exchange.fetch_ohlcv(cand, timeframe="1h", limit=3)
            print(f"    {cand}: OK, {len(candles)} velas -- ejemplo {candles[-1] if candles else None}")
        except Exception as e:
            print(f"    {cand}: ERROR -- {e}")
