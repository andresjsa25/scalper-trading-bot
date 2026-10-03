# Análisis de ventanas horarias y estrategias (2026-10-03)

Base del parche `parche-ventanas-y-estrategias`. Datos: 16 activos, velas de
15m/1h del 2025-11-23 al 2026-10-02. Simulación pesimista (el stop se mira
desde la vela del toque, SL primero), con comisiones y slippage de `config.py`.
Cada trade sale a SL o TP; el bot en vivo no tiene salida por tiempo. R = R neto
por trade. Períodos: P1 nov-mar, P2 abr-jun, P3 jul-oct.

| Estrategia / ventana | Trades | R medio | PF | P1 | P2 | P3 |
|---|---|---|---|---|---|---|
| V1 NY 13:30-16 + noche 21-24 (cripto y commodities) | 619 | 0,54 | 2,00 | 0,47 | 0,46 | 0,68 |
| V1 filtro original (Londres 8-10 + NY) | 611 | 0,40 | 1,67 | 0,37 | 0,45 | 0,41 |
| V1 solo Londres 8-10 | 188 | 0,12 | 1,17 | 0,30 | 0,10 | -0,04 |
| V10 cripto, solo Londres 8-13:30 | 192 | 0,22 | 1,40 | 0,26 | 0,08 | 0,35 |
| V10 cripto, todas las ventanas | 1172 | 0,10 | 1,17 | 0,16 | 0,09 | 0,01 |
| V5 todos los activos | 1613 | -0,07 | 0,87 | -0,05 | -0,04 | -0,13 |

Otras familias probadas sin ventaja tras costos: tendencia por ruptura (1h y
4h), ruptura del rango de apertura, reversión a la media, momentum entre
activos, pares y un clasificador de gradient boosting (AUC 0,50-0,52 fuera de
muestra). Control: entradas aleatorias en la ventana de NY con la misma
geometría de SL/TP rinden -0,15 a -0,78 R; la ventaja de V1 viene del patrón,
no del horario.

## Límites

- 10 meses de datos; las ventanas se eligieron mirando estos datos (se
  sostienen en los 3 períodos, pero hay que confirmarlas en vivo). Elegir
  activos por su historial no mejoró fuera de muestra, por eso no se recortan.
- El PF real de V1 en vivo fue 1,13, bastante menos que el backtest. Con ese
  nivel el objetivo de 10x en 10 meses no es realista; ver sensibilidad en la
  conversación del análisis.
- El backtest asume la cuenta separada; en la cuenta compartida las posiciones
  manuales consumen margen y bloquean señales.
