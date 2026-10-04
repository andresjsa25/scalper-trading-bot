# Protocolo de variantes (v1)

**Estado: BORRADOR hasta que Andrés lo apruebe y se complete la sección 4.**
Se congela con un commit etiquetado `protocolo-v1`, hecho **antes** de correr
cualquier variante. Desde ese commit, nada de este documento se cambia para
que un resultado "pase": un cambio es un `protocolo-v2` nuevo y se explica.

Este documento no contiene datos ni resultados. Los datos (`data/`), los logs
y `results/live_trading/` no se suben al repo.

## 1. Para qué sirve

Con 10 meses de datos y 16 activos, casi cualquier configuración se ve bien en
alguna ventana. Si se prueban muchas variantes y se elige la mejor, lo que se
encuentra suele ser suerte. Este protocolo fija **antes de mirar** qué se
prueba, cómo se mide y cuándo una variante se acepta o se descarta. "No
sirve" es un resultado válido y no se discute.

## 2. Datos y períodos

- Datos: velas de 15m, 1h y 4h, del **2025-11-23 al 2026-10-02**. El backtest lee solo la
  instantánea `data/backtest_snapshot/` (sección 2.1)
  (313 días, unos 10 meses). El criterio de "una ventana de aproximadamente un
  año" se aplica sobre todo el historial disponible. No se estira ni se
  recorta.
- **Recarga de datos (2026-10-04).** 1h y 4h de todos los activos llegan al
  2026-10-02 (las de 1h y 4h de NC* desde su fecha de listado; cripto y
  HYPE/XAUT/SOL desde 2025-01-01). **15m: la API pública de BingX no devuelve
  velas de 15m antes de mediados de 2026.** Las sondas dieron vacío para
  2025-06-01, 2026-01-01, 2026-04-01, 2026-05-10 y 2026-06-20, y la primera
  vela disponible fue 2026-06-30 (ADA, BNB) o 2026-07-20 (BTC, sonda).
  Los archivos de 15m que ya había empiezan el 2026-05-14 (ya estaban en
  `data/`, la recarga no los reemplazó: se unió con deduplicación). El
  arranque 2026-05-01 de la recarga fue un límite elegido, no un piso verificado.
  Resultado: **el 15m de 2025-11-23 a 2026-05-13 solo existe en `data/live/`**
  (caché del bot, ver 2.1). Con esa caché, la cobertura por activo está en 2.2.
  Esto afecta a V1 y V10 (entrada en 15m); el período se mantiene y el uso de
  esos tramos queda documentado en 2.3.
- **Huecos:** un día con huecos en 1h no cuenta como día completo para el
  contexto diario. Los NC* tienen entre 7 y 60 huecos por archivo en 1h y 4h;
  los de cripto no tienen huecos.
- **Manifiesto:** la sección 2.1 lista la instantánea del backtest por archivo.
- Entrada de 2h: pares de velas de 1h alineados a horas pares UTC (00-01,
  02-03, ...). Un par con una vela faltante se descarta. Como 24 es múltiplo
  de 2, los pares nunca cruzan el límite de día UTC.
- Contexto diario: velas 1D derivadas de 1h por día UTC. Solo cuentan los
  días con 24 velas de 1h completas. Una vela diaria del contexto se usa
  recién cuando cierra (00:00 UTC), así que no hay look-ahead. Los activos
  con huecos en 1h (NC*, unos 50 por archivo) pierden esos días.
- Tres períodos iguales (unos 104 días cada uno):
  - P1: 2025-11-23 a 2026-03-07
  - P2: 2026-03-08 a 2026-06-19
  - P3: 2026-06-20 a 2026-10-02
- Los períodos de `docs/analisis_ventanas_2026-10.md` (nov-mar, abr-jun,
  jul-oct) quedan solo como referencia histórica. No se usan para decidir.
- Los datos posteriores al 2026-10-02 **no entran al backtest**: son para el
  diario sombra (datos hacia adelante).

### 2.1 Instantánea y manifiesto

Instantánea del backtest: `data/backtest_snapshot/`, dentro de `data/` (ignorada
por git). Cortada en velas con apertura **≤ 2026-10-02 23:59 UTC**.
Prioridad por vela: API pública de BingX (recargada el 2026-10-04, velas
cerradas) > `data/` original (descarga anterior) > `data/live/`. Ninguna vela
viene de `data/live/` si la API tiene esa vela. `data/live/` la escribe el bot
en vivo y puede tener velas tomadas antes de cerrar; por eso no es fuente del
backtest.

Origen de cada tramo:
- **15m antes de la API:** la API pública ya no devuelve 15m de antes de
  mediados de 2026 (sondas del 2026-10-04). Ese tramo (p. ej. 2025-11-23 a
  2026-05-13 para BTC) solo existe en `data/live/`, que el bot fue agregando
  mientras corría. De ahí sale el 2025-11-23 de este protocolo.
- **Velas de `data/live/` desde el 2026-08-22** difieren de la API en una parte
  de las filas (hasta 0,8% en el cierre). La instantánea usa la API, así que la
  diferencia no entra al backtest, pero sí importa para el diario sombra: no
  leer cierres desde `data/live/`.
- **NASDAQ y AMZN** dejan de actualizarse en `data/live/` el 2026-09-05: ese día
  salieron de V1 en vivo (`run_live_trading.py`, líneas 15-18 y 108-117), y el
  actualizador solo escribe símbolos activos. La API sí tiene velas hasta el
  2026-10-02, así que la instantánea las tiene completas.
- **Fechas de inicio:** `launchTime` de `load_markets()` de BingX (metadata del
  exchange, consultado el 2026-10-04): XAG 2026-02-11 09:00, Brent 2026-03-06
  03:00, GOOGL 2025-11-03 09:15, META y NVDA 2025-11-13 09:00, AAPL 2025-11-13
  09:00, AMZN 2025-11-03 07:55, NASDAQ 2025-11-26 08:30, SP500 2025-11-26 08:20.
  Las velas de 1h y 4h de la API empiezan en esas fechas. **Las velas de 15m de
  GOOGL, META y NVDA empiezan el 2026-05-28, pero no por su listado**: es el
  inicio de su caché en `data/live/`. Los 15m de XAG y Brent sí empiezan en su
  listado.
- **Huecos:** un día con huecos en 1h no cuenta como día completo para el
  contexto diario. Los NC* tienen entre 7 y 60 huecos por archivo; los de cripto
  no tienen huecos.
- **5m:** ninguna variante lo usa. No se recargó ni entra al manifiesto.

| Archivo (`data/backtest_snapshot/`) | Velas | Primera (UTC) | Última (UTC) | SHA-256 (12) | Fuente: API / `data/` original / `data/live/` |
|---|---|---|---|---|---|
| ADA_USDT_USDT_15m.csv | 29896 | 2025-11-25 14:00 | 2026-10-02 23:45 | `545e19ef82c4` | 9120 / 4456 / 16320 |
| ADA_USDT_USDT_1h.csv | 15360 | 2025-01-01 00:00 | 2026-10-02 23:00 | `f6513638d471` | 15360 / 0 / 0 |
| ADA_USDT_USDT_4h.csv | 3840 | 2025-01-01 00:00 | 2026-10-02 20:00 | `e69f208693c2` | 3840 / 0 / 0 |
| BNB_USDT_USDT_15m.csv | 29896 | 2025-11-25 14:00 | 2026-10-02 23:45 | `d14214780f8d` | 9120 / 4456 / 16320 |
| BNB_USDT_USDT_1h.csv | 15360 | 2025-01-01 00:00 | 2026-10-02 23:00 | `4ed0274d276f` | 15360 / 0 / 0 |
| BNB_USDT_USDT_4h.csv | 3840 | 2025-01-01 00:00 | 2026-10-02 20:00 | `6bfbf599b9f0` | 3840 / 0 / 0 |
| BTC_USDT_USDT_15m.csv | 30088 | 2025-11-23 14:00 | 2026-10-02 23:45 | `aca7453c91db` | 9120 / 4456 / 16512 |
| BTC_USDT_USDT_1h.csv | 15360 | 2025-01-01 00:00 | 2026-10-02 23:00 | `5422e8915b3c` | 15360 / 0 / 0 |
| BTC_USDT_USDT_4h.csv | 3840 | 2025-01-01 00:00 | 2026-10-02 20:00 | `4057a09c359c` | 3840 / 0 / 0 |
| ETH_USDT_USDT_15m.csv | 30088 | 2025-11-23 14:00 | 2026-10-02 23:45 | `c59dd8fae865` | 9120 / 4456 / 16512 |
| ETH_USDT_USDT_1h.csv | 15360 | 2025-01-01 00:00 | 2026-10-02 23:00 | `77af80cc55f6` | 15360 / 0 / 0 |
| ETH_USDT_USDT_4h.csv | 3840 | 2025-01-01 00:00 | 2026-10-02 20:00 | `fc2ceeb0debd` | 3840 / 0 / 0 |
| HYPE_USDT_USDT_15m.csv | 30088 | 2025-11-23 14:00 | 2026-10-02 23:45 | `452c93a9ef49` | 9120 / 4456 / 16512 |
| HYPE_USDT_USDT_1h.csv | 15661 | 2024-12-19 11:00 | 2026-10-02 23:00 | `e2c665ad2faa` | 15360 / 301 / 0 |
| HYPE_USDT_USDT_4h.csv | 3916 | 2024-12-19 08:00 | 2026-10-02 20:00 | `3cb5e4554593` | 3840 / 76 / 0 |
| LINK_USDT_USDT_15m.csv | 29896 | 2025-11-25 14:00 | 2026-10-02 23:45 | `32355a1fc147` | 9120 / 20776 / 0 |
| LINK_USDT_USDT_1h.csv | 15360 | 2025-01-01 00:00 | 2026-10-02 23:00 | `4a324b4821c9` | 15360 / 0 / 0 |
| LINK_USDT_USDT_4h.csv | 3840 | 2025-01-01 00:00 | 2026-10-02 20:00 | `34b6bab6bf78` | 3840 / 0 / 0 |
| NCCO1OILBRENT2USD_USDT_USDT_15m.csv | 17359 | 2026-03-06 03:00 | 2026-10-02 23:45 | `bffd4e34a4be` | 9120 / 4008 / 4231 |
| NCCO1OILBRENT2USD_USDT_USDT_1h.csv | 4341 | 2026-03-06 03:00 | 2026-10-02 23:00 | `b802b4341130` | 4341 / 0 / 0 |
| NCCO1OILBRENT2USD_USDT_USDT_4h.csv | 1117 | 2026-03-06 00:00 | 2026-10-02 20:00 | `2e58862d34fe` | 1117 / 0 / 0 |
| NCCOXAG2USD_USDT_USDT_15m.csv | 21778 | 2026-02-11 09:00 | 2026-10-02 23:45 | `7a799875dcb1` | 9120 / 4456 / 8202 |
| NCCOXAG2USD_USDT_USDT_1h.csv | 5445 | 2026-02-11 09:00 | 2026-10-02 23:00 | `2154e675421c` | 5445 / 0 / 0 |
| NCCOXAG2USD_USDT_USDT_4h.csv | 1369 | 2026-02-11 08:00 | 2026-10-02 20:00 | `0f335e9ae159` | 1369 / 0 / 0 |
| NCSINASDAQ1002USD_USDT_USDT_15m.csv | 24147 | 2025-11-26 08:30 | 2026-10-02 23:45 | `6d6d525626b7` | 9120 / 2916 / 12111 |
| NCSINASDAQ1002USD_USDT_USDT_1h.csv | 6040 | 2025-11-26 08:00 | 2026-10-02 23:00 | `6a211a15577b` | 6040 / 0 / 0 |
| NCSINASDAQ1002USD_USDT_USDT_4h.csv | 1555 | 2025-11-26 08:00 | 2026-10-02 20:00 | `57f3ada49ea6` | 1555 / 0 / 0 |
| NCSISP5002USD_USDT_USDT_15m.csv | 24140 | 2025-11-26 08:15 | 2026-10-02 23:45 | `f7d123bdfbc1` | 9111 / 3868 / 11161 |
| NCSISP5002USD_USDT_USDT_1h.csv | 6039 | 2025-11-26 08:00 | 2026-10-02 23:00 | `3da209859aa6` | 6039 / 0 / 0 |
| NCSISP5002USD_USDT_USDT_4h.csv | 1556 | 2025-11-26 08:00 | 2026-10-02 20:00 | `65acde6d2087` | 1556 / 0 / 0 |
| NCSKAAPL2USD_USDT_USDT_15m.csv | 22686 | 2025-11-28 00:00 | 2026-10-02 23:45 | `917d22b44363` | 9120 / 4456 / 9110 |
| NCSKAAPL2USD_USDT_USDT_1h.csv | 5966 | 2025-11-13 09:00 | 2026-10-02 23:00 | `951fb7dd1313` | 5966 / 0 / 0 |
| NCSKAAPL2USD_USDT_USDT_4h.csv | 1535 | 2025-11-13 08:00 | 2026-10-02 20:00 | `c79afafac9e7` | 1535 / 0 / 0 |
| NCSKAMZN2USD_USDT_USDT_15m.csv | 23068 | 2025-11-24 01:00 | 2026-10-02 23:45 | `7cba92b579de` | 9120 / 4224 / 9724 |
| NCSKAMZN2USD_USDT_USDT_1h.csv | 6155 | 2025-11-03 07:00 | 2026-10-02 23:00 | `ca3b8452b554` | 6155 / 0 / 0 |
| NCSKAMZN2USD_USDT_USDT_4h.csv | 1583 | 2025-11-03 04:00 | 2026-10-02 20:00 | `37698697e3f9` | 1583 / 0 / 0 |
| NCSKGOOGL2USD_USDT_USDT_15m.csv | 12232 | 2026-05-28 14:00 | 2026-10-02 23:45 | `e8be9dba17ba` | 9120 / 3112 / 0 |
| NCSKGOOGL2USD_USDT_USDT_1h.csv | 6153 | 2025-11-03 09:00 | 2026-10-02 23:00 | `43b9b3100cec` | 6153 / 0 / 0 |
| NCSKGOOGL2USD_USDT_USDT_4h.csv | 1582 | 2025-11-03 08:00 | 2026-10-02 20:00 | `45e1ada7f85e` | 1582 / 0 / 0 |
| NCSKMETA2USD_USDT_USDT_15m.csv | 12232 | 2026-05-28 14:00 | 2026-10-02 23:45 | `fb1d9231739f` | 9120 / 3112 / 0 |
| NCSKMETA2USD_USDT_USDT_1h.csv | 5881 | 2025-11-13 09:00 | 2026-10-02 23:00 | `1cf0a455608c` | 5881 / 0 / 0 |
| NCSKMETA2USD_USDT_USDT_4h.csv | 1519 | 2025-11-13 08:00 | 2026-10-02 20:00 | `38d05822ee36` | 1519 / 0 / 0 |
| NCSKNVDA2USD_USDT_USDT_15m.csv | 12232 | 2026-05-28 14:00 | 2026-10-02 23:45 | `1e4a44fe5efb` | 9120 / 3112 / 0 |
| NCSKNVDA2USD_USDT_USDT_1h.csv | 5906 | 2025-11-13 09:00 | 2026-10-02 23:00 | `42835c985684` | 5906 / 0 / 0 |
| NCSKNVDA2USD_USDT_USDT_4h.csv | 1521 | 2025-11-13 08:00 | 2026-10-02 20:00 | `3f4bebec3481` | 1521 / 0 / 0 |
| SOL_USDT_USDT_15m.csv | 29992 | 2025-11-24 14:00 | 2026-10-02 23:45 | `fca68cb4fba5` | 9120 / 4456 / 16416 |
| SOL_USDT_USDT_1h.csv | 15360 | 2025-01-01 00:00 | 2026-10-02 23:00 | `2964d8f8816d` | 15360 / 0 / 0 |
| SOL_USDT_USDT_4h.csv | 3840 | 2025-01-01 00:00 | 2026-10-02 20:00 | `7f463cd910ca` | 3840 / 0 / 0 |
| XAUT_USDT_USDT_15m.csv | 30088 | 2025-11-23 14:00 | 2026-10-02 23:45 | `5996b178f137` | 9120 / 4456 / 16512 |
| XAUT_USDT_USDT_1h.csv | 13138 | 2025-04-03 14:00 | 2026-10-02 23:00 | `7b9cd518b414` | 13138 / 0 / 0 |
| XAUT_USDT_USDT_4h.csv | 3285 | 2025-04-03 12:00 | 2026-10-02 20:00 | `f5812490fca3` | 3285 / 0 / 0 |

### 2.2 Cobertura por activo y período

Porcentaje de velas presentes frente a 24/7 esperadas en cada período; entre
paréntesis, la primera vela del período. Los NC* tienen sesiones y festivos, así
que su porcentaje no mide huecos: sirve solo para saber desde cuándo hay datos.

| Activo | TF | P1 (23-nov a 07-mar) | P2 (08-mar a 19-jun) | P3 (20-jun a 02-oct) |
|---|---|---|---|---|
| ADA | 15m | 98% (desde 11-25) | 100% (desde 03-08) | 100% (desde 06-20) |
| ADA | 1h | 100% (desde 11-23) | 100% (desde 03-08) | 100% (desde 06-20) |
| ADA | 4h | 100% (desde 11-23) | 100% (desde 03-08) | 100% (desde 06-20) |
| BNB | 15m | 98% (desde 11-25) | 100% (desde 03-08) | 100% (desde 06-20) |
| BNB | 1h | 100% (desde 11-23) | 100% (desde 03-08) | 100% (desde 06-20) |
| BNB | 4h | 100% (desde 11-23) | 100% (desde 03-08) | 100% (desde 06-20) |
| BTC | 15m | 99% (desde 11-23) | 100% (desde 03-08) | 100% (desde 06-20) |
| BTC | 1h | 100% (desde 11-23) | 100% (desde 03-08) | 100% (desde 06-20) |
| BTC | 4h | 100% (desde 11-23) | 100% (desde 03-08) | 100% (desde 06-20) |
| ETH | 15m | 99% (desde 11-23) | 100% (desde 03-08) | 100% (desde 06-20) |
| ETH | 1h | 100% (desde 11-23) | 100% (desde 03-08) | 100% (desde 06-20) |
| ETH | 4h | 100% (desde 11-23) | 100% (desde 03-08) | 100% (desde 06-20) |
| HYPE | 15m | 99% (desde 11-23) | 100% (desde 03-08) | 100% (desde 06-20) |
| HYPE | 1h | 100% (desde 11-23) | 100% (desde 03-08) | 100% (desde 06-20) |
| HYPE | 4h | 100% (desde 11-23) | 100% (desde 03-08) | 100% (desde 06-20) |
| LINK | 15m | 98% (desde 11-25) | 100% (desde 03-08) | 100% (desde 06-20) |
| LINK | 1h | 100% (desde 11-23) | 100% (desde 03-08) | 100% (desde 06-20) |
| LINK | 4h | 100% (desde 11-23) | 100% (desde 03-08) | 100% (desde 06-20) |
| NCCO1OILBRENT2USD | 15m | 1% (desde 03-06) | 72% (desde 03-09) | 100% (desde 06-20) |
| NCCO1OILBRENT2USD | 1h | 1% (desde 03-06) | 72% (desde 03-09) | 100% (desde 06-20) |
| NCCO1OILBRENT2USD | 4h | 1% (desde 03-06) | 77% (desde 03-09) | 100% (desde 06-20) |
| NCCOXAG2USD | 15m | 17% (desde 02-11) | 100% (desde 03-08) | 100% (desde 06-20) |
| NCCOXAG2USD | 1h | 17% (desde 02-11) | 100% (desde 03-08) | 100% (desde 06-20) |
| NCCOXAG2USD | 4h | 18% (desde 02-11) | 100% (desde 03-08) | 100% (desde 06-20) |
| NCSINASDAQ1002USD | 15m | 65% (desde 11-26) | 75% (desde 03-08) | 100% (desde 06-20) |
| NCSINASDAQ1002USD | 1h | 65% (desde 11-26) | 75% (desde 03-08) | 100% (desde 06-20) |
| NCSINASDAQ1002USD | 4h | 70% (desde 11-26) | 78% (desde 03-08) | 100% (desde 06-20) |
| NCSISP5002USD | 15m | 65% (desde 11-26) | 75% (desde 03-08) | 100% (desde 06-20) |
| NCSISP5002USD | 1h | 65% (desde 11-26) | 75% (desde 03-08) | 100% (desde 06-20) |
| NCSISP5002USD | 4h | 70% (desde 11-26) | 78% (desde 03-08) | 100% (desde 06-20) |
| NCSKAAPL2USD | 15m | 50% (desde 11-28) | 75% (desde 03-09) | 100% (desde 06-20) |
| NCSKAAPL2USD | 1h | 55% (desde 11-24) | 77% (desde 03-09) | 100% (desde 06-20) |
| NCSKAAPL2USD | 4h | 58% (desde 11-24) | 80% (desde 03-09) | 100% (desde 06-20) |
| NCSKAMZN2USD | 15m | 54% (desde 11-24) | 76% (desde 03-09) | 100% (desde 06-20) |
| NCSKAMZN2USD | 1h | 55% (desde 11-24) | 77% (desde 03-09) | 100% (desde 06-20) |
| NCSKAMZN2USD | 4h | 58% (desde 11-24) | 80% (desde 03-09) | 100% (desde 06-20) |
| NCSKGOOGL2USD | 15m | sin datos | 22% (desde 05-28) | 100% (desde 06-20) |
| NCSKGOOGL2USD | 1h | 55% (desde 11-24) | 77% (desde 03-09) | 100% (desde 06-20) |
| NCSKGOOGL2USD | 4h | 58% (desde 11-24) | 80% (desde 03-09) | 100% (desde 06-20) |
| NCSKMETA2USD | 15m | sin datos | 22% (desde 05-28) | 100% (desde 06-20) |
| NCSKMETA2USD | 1h | 52% (desde 11-24) | 77% (desde 03-09) | 100% (desde 06-20) |
| NCSKMETA2USD | 4h | 56% (desde 11-24) | 80% (desde 03-09) | 100% (desde 06-20) |
| NCSKNVDA2USD | 15m | sin datos | 22% (desde 05-28) | 100% (desde 06-20) |
| NCSKNVDA2USD | 1h | 53% (desde 11-24) | 77% (desde 03-09) | 100% (desde 06-20) |
| NCSKNVDA2USD | 4h | 56% (desde 11-24) | 80% (desde 03-09) | 100% (desde 06-20) |
| SOL | 15m | 98% (desde 11-24) | 100% (desde 03-08) | 100% (desde 06-20) |
| SOL | 1h | 100% (desde 11-23) | 100% (desde 03-08) | 100% (desde 06-20) |
| SOL | 4h | 100% (desde 11-23) | 100% (desde 03-08) | 100% (desde 06-20) |
| XAUT | 15m | 99% (desde 11-23) | 100% (desde 03-08) | 100% (desde 06-20) |
| XAUT | 1h | 100% (desde 11-23) | 100% (desde 03-08) | 100% (desde 06-20) |
| XAUT | 4h | 100% (desde 11-23) | 100% (desde 03-08) | 100% (desde 06-20) |

Núcleo con cobertura completa en P1, P2 y P3 (15m): ADA, BNB, BTC, ETH, HYPE,
LINK, SOL, XAUT. Los NC* son los que más faltan en P1.

### 2.4 Validación de la caché `data/live/` contra la API

Alcance: la validación es a nivel de hora (4 velas de 15m contra la vela de 1h
de la API). No garantiza la forma de las velas dentro de la hora.

Método: cada 4 velas de 15m de `data/live/` se agrupan en una vela de 1h
(apertura de la primera, máximo, mínimo, cierre de la última, volumen sumado),
y se comparan con la vela de 1h de la API (la instantánea). Solo cuentan las
horas con 4 velas de 15m. Medida: diferencia relativa máxima en OHLC. Se
reporta el porcentaje de horas con diferencia mayor a 0,01%.

Resultado (2026-10-04, `data/backtest_snapshot/xval_live15m_vs_api1h.csv`):
- P1 y P2: 0% de horas con diferencia mayor a 0,01% en todos los activos con
  datos. La caché coincide con la API en ese tramo.
- P3: en cripto, 30% a 37% de horas con diferencia mayor a 0,01%; en acciones y
  commodities, 6% a 32%. Las diferencias empiezan entre el 2026-08-02 y el
  2026-08-09, y siguen hasta el 2026-10-02.
- En las horas con diferencia, el volumen de `data/live/` es menor que el de la
  API en el 100% de los casos (mediana de −88% a −95%), y el cierre difiere en
  ~95% de ellas. Es la firma de velas tomadas antes de cerrar: la caché guardó
  una foto del cierre que el bot vio en ese momento y no la volvió a escribir.

Porcentaje de horas con diferencia mayor a 0,01% (OHLC), por activo y período:

| Activo | P1 | P2 | P3 |
|---|---|---|---|
| ADA | 0.0% | 0.0% | 37.4% |
| BNB | 0.0% | 0.0% | 37.1% |
| BTC | 0.0% | 0.0% | 30.1% |
| ETH | 0.0% | 0.0% | 34.4% |
| HYPE | 0.0% | 0.0% | 30.9% |
| NCCO1OILBRENT2USD | 0.0% | 0.0% | 27.0% |
| NCCOXAG2USD | 0.0% | 0.0% | 25.6% |
| NCSINASDAQ1002USD | 0.0% | 0.0% | 15.9% |
| NCSISP5002USD | 0.0% | 0.0% | 6.0% |
| NCSKAAPL2USD | 0.0% | 0.0% | 32.1% |
| NCSKAMZN2USD | 0.0% | 0.0% | 21.3% |
| NCSKGOOGL2USD | sin datos | 0.0% | 20.2% |
| NCSKMETA2USD | sin datos | 0.0% | 20.7% |
| NCSKNVDA2USD | sin datos | 0.0% | 19.8% |
| SOL | 0.0% | 0.0% | 30.6% |
| XAUT | 0.0% | 0.0% | 27.7% |

Regla de aceptación propuesta (**pendiente de OK de Andrés**):
1. Tolerancia por vela: 0,01% en cada campo OHLC. Volumen: menos de 99% del
   volumen de la API cuenta como diferencia.
2. Un tramo de `data/live/` entra al backtest solo si, en ese tramo, menos del
   0,5% de las horas difiere más de la tolerancia. Este tramo (P1 y P2 de cripto)
   pasa. P3 no pasa y se toma de la API, como ya hace la instantánea.
3. Velas tomadas sin cerrar: una vela cuyo volumen o cierre no coincide con la
   API se considera tomada sin cerrar. No entra desde la caché. Si la API tiene
   la vela, se usa la API. Si no la tiene (tramo anterior a la API), la hora se
   excluye y el número de horas excluidas se reporta en cada corrida.
4. Último tramo de la caché (la vela en curso al momento del corte): nunca entra.
   El corte del backtest es 2026-10-02 23:59 UTC.

### 2.3 Cómo se aplican los criterios con activos que arrancan tarde

Aprobada por Andrés, con el cambio en la regla 6:
1. Un activo sin datos en un período no aporta trades a ese período. No cuenta
   como cero ni como pérdida.
2. Criterio 2 (PF > 1,3 en P1, P2 y P3): se calcula con los trades de todos los
   activos que tienen datos en ese período. La lista de activos por período se
   fija en el reporte antes de ver resultados.
3. Criterios 1 (100 trades) y 3 (IC del PF > 1): sobre el historial completo,
   con todos los activos juntos.
4. Un activo que arranca tarde no se excluye del historial y no cambia los
   umbrales.
5. Reporte adicional, no criterio: PF por período solo con el núcleo de la
   sección 2.2, para ver si el resultado depende de los activos que arrancan
   tarde.
6. Si un período tiene menos de 30 trades de una variante, la variante **no
   aprueba** por evidencia insuficiente. No hay discusión posterior sobre ese caso.

## 3. Variantes (cerradas: N = 9)

Cada variante cambia **una sola cosa** respecto de su base. Los nombres son los
que usará el diario sombra.

| ID | Qué es |
|---|---|
| V1-base | V1 como está en vivo: mismas ventanas (cripto y commodities NY 13:30-16:00 + noche 21:00-24:00 UTC; SP500 y acciones solo NY), TP 2,3R |
| V1-alt1 | V1-base con TP 2R |
| V1-alt2 | V1-base sin filtro EMA10 (para ver qué aporta) |
| V10-base | V10 como está en vivo: 6 cripto, solo Londres 08:00-13:30 UTC |
| V10-alt1 | V10-base en todas las ventanas (registra lo que hoy se descarta) |
| V10-alt2 | V10-base con stop por mecha en todos los activos |
| V5-orig | **Referencia, no es variante nueva.** V5 original: entrada 1h, contexto 4h, todos los activos (la que dio PF 0,87). Se reporta, no cuenta en N y no se evalúa contra la sección 7 |
| V5-alt1 | V5 con entrada en 2h y contexto diario, patrón de vela actual |
| V5-alt2 | V5 con entrada en 2h y contexto 4h, patrón de vela actual |
| V5-alt3 | V5-alt1 con el filtro de patrón estricto de la sección 3.1 |

V5-alt2 y V5-alt1 difieren solo en el contexto, así que se comparan entre sí
con "una sola cosa". V5-alt1 y V5-alt2 cambian la entrada respecto de
V5-orig (1h a 2h), y V5-alt1 además cambia el contexto (4h a 1D): esas
comparaciones con V5-orig son de dos cambios a la vez, y se reportan así.

### 3.1 Filtro de patrón estricto (V5-alt3)

Patrones: martillo, estrella fugaz y pinzas. Se elimina el harami, que no
tiene criterio de tamaño y es el más laxo.

- **Martillo** (alcista): mecha inferior ≥ 3× el cuerpo, mecha superior ≤ 15%
  del rango, cuerpo ≥ 10% del rango. **Estrella fugaz**: simétrico.
- **Pinzas**: diferencia de mínimos (o máximos) ≤ 0,05% del precio (antes 0,1%).
- **Tope de cuerpo**: no hay tope explícito. Con R = mecha superior + cuerpo +
  mecha inferior, y mecha inferior ≥ 3·cuerpo con mecha superior ≤ 0,15·R, se
  obtiene 4·cuerpo ≤ 0,85·R, o sea **cuerpo ≤ ~21% del rango**. Ese es el
  tope efectivo.
- **Medición**: en la vela de patrón de 2h. Entrada al open de la vela
  siguiente, igual que V5-alt1.
- **Ventana de búsqueda**: `PATTERN_SEARCH_BARS = 20` cuenta velas de entrada,
  así que con 2h equivale a 40 h, no a 20 h. Valor propuesto: 20 velas de 2h.
  **Pendiente de OK de Andrés.**

### 3.2 Constantes que dependen de la temporalidad (V5)

Revisadas en `src/strategy_v5_fib_pullback.py`, `src/indicators/liquidity.py`,
`src/backtest_v5.py` y `src/indicators/candle_patterns.py`. "Velas" son las
de la temporalidad de entrada salvo que se indique otra cosa. Las horas son el
equivalente temporal.

| Constante | V5-orig (1h / 4h) | V5-alt1 (2h / 1D) | V5-alt2 (2h / 4h) | V5-alt3 (= alt1 + patrón estricto) | Estado |
|---|---|---|---|---|---|
| `ZONE_VALIDITY_BARS` = 60 | 60 velas = 60 h | 60 velas = 120 h | 60 velas = 120 h | 60 velas = 120 h | **Decidido: sin cambio (60 velas).** En 2h eso duplica el tiempo. El comentario del código dice "~10 días", pero 60 h son 2,5 días: es un error de comentario |
| `PATTERN_SEARCH_BARS` = 20 | 20 velas = 20 h | 20 velas = 40 h | 20 velas = 40 h | 20 velas = 40 h | **Aprobado** por Andrés: 20 velas de 2h |
| `SETUP_VALIDITY_BARS` = 200 | 200 velas = 200 h | 200 velas = 400 h | 200 velas = 400 h | 200 velas = 400 h | **Decidido: sin cambio (200 velas).** |
| `find_raw_fractals(n=2)` sobre el contexto | 2 velas por lado = 8 h por lado (4h) | 2 velas por lado = 2 días por lado (1D) | 2 velas por lado = 8 h (4h) | 2 días por lado (1D) | **Decidido: n=2 sin cambio.** Con 1D, un fractal de n=2 exige 5 días de ventana, mucho más grueso; queda documentado |
| `min_swing_percentile` | 0 (apagado) | 0 | 0 | 0 | Default de `generate_setups`. La grilla de calibración no se usa en las variantes salvo que el protocolo lo fije |
| `min_rr_ratio` | 0 | 0 | 0 | 0 | Default. El filtro de R:R es uno de los factores de la sección 9, no parte de las variantes |
| Apalancamiento (`run_live_trading.py`: `V1_LEVERAGE`, `V10_LEVERAGE`, `V5_LEVERAGE`) | 50 | 50 | 50 | 50 | **Decidido por Andrés: por estrategia, como en vivo** (V5 50; V1 y V10 usan 15). Define `liq_buffer = 1/apalancamiento − 0,004` |
| Riesgo por operación en backtests | 2% | 2% | 2% | 2% | **Decidido: 2% fijo**, explícito y guardado en cada resultado. Columna extra: drawdown máximo a 1%, sin cambiar criterios. Ver sección 6 |
| Patrones (`HAMMER_WICK_TO_BODY_RATIO`, `HAMMER_OPPOSITE_WICK_MAX_RATIO`, `TWEEZER_HL_TOLERANCE_PCT`) | 2,0 / 0,25 / 0,001 | igual | igual | 3,0 / 0,15 / 0,0005 (sección 3.1) | Relativos al rango o al precio, no al número de velas. No cambian con la temporalidad |
| `STOP_BUFFER_PCT`, `MIN_STOP_DISTANCE_PCT`, `MAX_RR_RATIO` | 0,001 / 0,005 / 10 | igual | igual | igual | Fijos. No dependen de la temporalidad |
| `TIMEFRAME_ENTRY`/`TIMEFRAME_CONTEXT` de `config.py` | 15m / 1h | no los usa V5 | no los usa V5 | no los usa V5 | V5 lee los archivos directamente, así que estas constantes no aplican |
| Velas de 5m | no | no | no | no | **Ninguna variante las usa.** No se recargaron ni entran al manifiesto |

Reglas sobre el conjunto:
- **N = 9 pruebas.** Se declara en cada reporte: con 9 intentos, que alguna
  pase por suerte es posible. Por eso pasar este protocolo solo habilita
  entrar al diario sombra, no operar con capital (sección 8).
- Una variante nueva, o un cambio de parámetros después de ver resultados,
  **no es parte de este protocolo**: se anota como exploratoria, cuenta para N
  y no puede aprobarse con este protocolo.
- Los parámetros de cada variante se escriben en el código antes de correrlas
  (con el hash del commit en cada resultado). No se ajustan después.

## 4. Costos (a completar antes de congelar)

El backtest informa **R neto de costos**. Valores base, tomados de `config.py`:
comisión maker 0,02%, comisión taker 0,05%, deslizamiento estimado 0,02%
por lado.

Antes de congelar, Claude Code compara esos valores con las comisiones reales
del export de BingX (incluido el funding) y escribe acá los valores finales,
con la fuente. Si hay diferencia, se usan los del export.

| Concepto | Valor base (`config.py`) | Valor final (export) |
|---|---|---|
| Comisión maker | 0,02% | **0,02%**. Fuente: export BingX USDT-M (678 filas, 2026-07-30 a 2026-10-02), 0,02% exacto en 48 filas |
| Comisión taker | 0,05% | **0,05%**. Fuente: mismo export, 0,05% exacto en 336 filas (50%) |
| Deslizamiento por lado | 0,02% | **0,02%**. No medible con el export (no trae precio de disparo de la señal). Se mantiene el valor base, sin evidencia para cambiarlo |
| Funding | _no modelado_ | **Medido, reportado aparte.** Ver nota de funding abajo |

Observación del export, **no usada**: aparecen también tasas de 0,006% (205
filas) y 0,003% (67 filas). El export no las explica (`Fee Coin` es USDT en
todas las filas, así que no es descuento en BGB, y no distingue limit de
market). Se usan los valores estándar 0,02% / 0,05% por ser los conservadores
y los únicos que el export confirma exactamente. Origen de las tasas menores:
pendiente de confirmar con Andrés.

**Funding (nota):** el export no trae filas de funding. Se midió con la API
pública de BingX (`/openApi/swap/v2/quote/fundingRate`, sin claves) para los
pares del export, período 2026-07-29 a 2026-10-03, cubriendo cada operación
cerrada. Resultado: 290 trades emparejados, duración mediana 2,4 h y media 8,1 h.
Funding neto por trade: mediana 0% del nocional, media −0,004% del nocional (los
longs pagan cuando la tasa es positiva y los shorts cobran). Total del período:
−21,7 USDT. Como el funding es chico frente a la comisión de ida y vuelta
(0,07%), **no entra en el R neto base**. Se reporta aparte como R neto con
funding, calculado con el historial de funding de cada símbolo en el período
del backtest. La conversión de % de nocional a R necesita la distancia del stop
por trade, que el export no trae: se toma del log del bot. El funding de
períodos anteriores se obtiene de la misma API pública.

Se reportan R bruto y R neto en columnas separadas. El R neto base incluye
comisiones y deslizamiento según esta tabla; el R neto con funding es una
columna aparte.

## 5. Simulación

- El mismo simulador para todas las variantes (el "pesimista" del análisis
  anterior): el stop se evalúa desde la vela del toque y, si una vela toca SL y
  TP, **gana el SL**.
- Sin look-ahead: una señal usa solo datos hasta el cierre de su vela.
- Órdenes límite (V1): se reporta aparte la **tasa de llenado simulada**. En
  vivo, las órdenes que se llenan tienden a ser las que siguen en contra, así
  que el backtest puede sobrestimar.
- Reglas de ejecución del bot (riesgo 2% por operación, tope de 5 USD por trade, máximo 10
  operaciones, 30% de riesgo abierto, una posición por símbolo) se aplican
  igual que en vivo. Se reporta cuántas señales se descartan por esas reglas.

## 6. Qué se mide

Por variante: trades, R medio neto, PF neto, PF en P1, P2 y P3, drawdown máximo
en R, tasa de llenado (V1) y concentración por activo (porcentaje de trades de
los 3 activos principales). Los 16 activos no son 16 muestras independientes
(las cripto están correlacionadas).

El backtest corre con riesgo fijo de 2% por operación, guardado en cada
resultado. Como columna extra se reporta el drawdown máximo a riesgo de 1%.
Esa columna no cambia criterios ni variantes.

Intervalo de confianza del PF: bootstrap **por día** (se remuestrean días, no
trades, por la correlación entre activos), 10.000 remuestreos, 95%.

## 7. Criterio de aceptación

Una variante sobrevive solo si cumple **todo**:

1. Al menos **100 trades** en todo el historial. Una variante con menos de
   100 se descarta por muestra insuficiente. Los umbrales de 2 y 3 no se
   relajan para ella.
2. **PF neto mayor a 1,3 en cada uno de P1, P2 y P3.**
3. **Límite inferior del IC 95% del PF neto por encima de 1** en todo el
   historial.

Si no cumple, se descarta sin discusión y queda en el reporte. Los resultados
se muestran siempre de las 9 variantes, no solo las que pasan.

## 8. Qué pasa después

- Las variantes que sobreviven entran al diario sombra con su ID, para juntar
  datos hacia adelante.
- Pasar a operar con capital es una **decisión explícita de Andrés**, con un
  criterio sobre los datos hacia adelante que se define en un `protocolo-v2`
  antes de que el diario junte datos suficientes. Este protocolo no lo autoriza.
- No se toca el bot en vivo sin confirmación de Andrés.

## 9. Diagnóstico de V5 (no es una prueba de aceptación)

Antes de las pruebas, se explica por qué el backtest anterior de V5 daba
rentable y el pesimista da PF 0,87. Método: correr los dos simuladores con los
mismos datos y parámetros, comparar entre 20 y 30 trades uno a uno hasta
encontrar la primera divergencia, y después una ablación cambiando un factor
por vez (ventana de fechas, regla cuando SL y TP caen en la misma vela, filtro
de R:R, salida escalonada). El resultado es una tabla de causas. No cambia los
criterios de la sección 7.

## 10. Higiene

- Datos, logs y diario fuera del repo público (carpeta aparte, no solo
  `.gitignore`). Nunca claves ni tokens en un commit.
- Lo real y lo teórico se reportan separados. Los números teóricos incluyen
  costos según la sección 4, pero no el efecto de la cuenta compartida con
  posiciones manuales.

- Archivado de velas: cada recarga agrega velas nuevas a un archivo por activo
  y temporalidad en `data/archive/`. **Solo agrega:** nunca reescribe ni borra una
  vela archivada. Cada archivo lleva SHA-256 en el manifiesto. Las corridas leen
  `data/backtest_snapshot/` y nunca `data/live/`.

## 11. Historial del protocolo

| Versión | Fecha | Cambio |
|---|---|---|
| v1 | 2026-10-04 | Primera versión, borrador |
| v1 (cobertura) | 2026-10-04 | Instantánea `data/backtest_snapshot/` con manifiesto y SHA-256. Cobertura por activo y período (2.2). Criterios con activos que arrancan tarde (2.3, propuesta). Constantes de V5 decididas (3.2). Apalancamiento por estrategia (15/15/50). Riesgo 2% en backtests, con DD a 1% como columna extra |
| v1 (completa) | 2026-10-04 | Sección 4 completa con valores del export (maker 0,02%, taker 0,05%, deslizamiento 0,02%, funding medido aparte). V5 pasa a 3 variantes nuevas (V5-alt1, V5-alt2, V5-alt3) con entrada 2h; V5-orig queda como referencia fuera de N. Filtro estricto de patrón (3.1) con tope de cuerpo implícito de ~21%. Regla de muestra: menos de 100 trades se descarta sin relajar umbrales. N = 9. Pendientes antes del tag: datos hasta 2026-10-02 (sección 2) y ventana de búsqueda de V5-alt3 |
