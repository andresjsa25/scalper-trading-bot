# Scalper Trading Bot

Bot de trading algorítmico para BingX (cripto + instrumentos sintéticos de
índices, acciones y commodities vía swaps tokenizados) con tres estrategias
propias, cada una calibrada y validada por activo mediante backtesting y
walk-forward (out-of-sample) antes de activarse en real.

## Qué hace

- **Ejecuta en vivo** (`run_live_trading.py`, disparado cada 15 minutos vía
  Programador de Tareas de Windows) sobre una cartera de cripto (BTC, ETH,
  SOL, ADA, BNB, HYPE) e instrumentos sintéticos USD de BingX (SP500, oro,
  plata, petróleo, AAPL, GOOGL, META, NVDA), con SL/TP adjuntos a la orden
  en el momento de la entrada — sobreviven aunque el proceso del bot se
  caiga o se reinicie.
- **Tres estrategias**, cada una con su propio motor de backtest:
  - **V1 — Sniper de liquidez**: entrada en 15m con contexto de 1h, barrido
    de liquidez + CHoCH + FVG.
  - **V5 — Retroceso de Fibonacci**: entrada en 1h con contexto de 4h.
  - **V10 — Rebote de Bollinger + RSI**: entrada en 1h con contexto de 4h
    (RSI).
- **Backtesting y walk-forward** (`run_backtest_3strategies.py`,
  `run_walkforward_v1.py` y variantes): compara las tres estrategias por
  activo y valida out-of-sample (recalibrando en ventanas móviles, sin
  look-ahead bias) antes de sumar o sacar un activo de la cartera en vivo —
  ver `results/` para los CSV de cada corrida.
- **Gestión de riesgo basada en evidencia, no en corazonada**: activos como
  AMZN y NASDAQ100 se sacaron de la cartera en vivo por señales concretas
  (rachas de pérdidas reales / profit factor por debajo de 1 en
  out-of-sample), documentado en los comentarios de `config.py` y
  `run_live_trading.py`.

## Stack

Python + [ccxt](https://github.com/ccxt/ccxt) (BingX), pandas/numpy para el
motor de backtest, matplotlib/mplfinance para gráficos, y
[duka](https://pypi.org/project/duka/) para datos históricos de forex
(Dukascopy) donde el exchange no los provee.

## Cómo correrlo

```bash
pip install -r requirements.txt
cp .env.example .env   # completar con tu API key/secret de BingX
python run_live_trading.py
```

Para probar sin arriesgar capital real, `LIVE_TRADING_DRY_RUN=true` en
`.env` corre el mismo loop contra datos reales pero sin mandar ninguna
orden al exchange.

## Estructura

```
src/                     Motor de trading en vivo, indicadores, filtros
strategy_v*.py           Cada estrategia (generación de setups)
backtest*.py             Motores de backtest y métricas
run_backtest_*.py        Scripts de comparación por activo/estrategia
run_walkforward_*.py     Validación out-of-sample
fetch_data_*.py          Descarga de históricos (BingX / Dukascopy)
config.py                Cartera activa, timeframes, parámetros por defecto
results/                 CSV de cada backtest/walk-forward ya corrido
```
