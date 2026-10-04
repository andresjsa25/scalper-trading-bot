# Spec: la caché de velas del bot en vivo solo guarda velas cerradas

**Estado: borrador v2. NO SE CONSTRUYE.** Falta cerrar el diseño (ver "Hallazgo de la reproducción") y que Andrés apruebe. Los criterios 1 y 2 de esta versión son condicionales a esa decisión.

## Hallazgo de la reproducción de señales (2026-10-04)

Claude Code reprodujo las señales de las 189 órdenes reales (solo lectura). Resultado:

| Estrategia | Órdenes | Igual | Distinta | Desaparece | No reproducible con caché |
|---|---|---|---|---|---|
| V1 | 162 | 40 | 6 | 71 | 45 |
| V10 | 26 | 5 | 12 | 9 | 0 |
| V5 | 1 | 0 | 0 | 1 | 0 |

Lectura (separando el sesgo del método):

- **Casos comparables** (la vela de la señal ya estaba cerrada en el momento de la orden): V1 54 y V10 4. De esos 58, 21 cambian de señal con velas cerradas de la API (V1: 3 distintas y 16 desaparecen; V10: 2 distintas), cerca del 36%.
- **Casos no evaluables** (la vela de la señal estaba abierta): V1 63, V10 22, V5 1. Con "solo velas cerradas" desaparecen por construcción. Esto **no mide el caché**: mide que el método no puede ver la vela en curso.
- **45 órdenes de V1 no se reproducen ni con el caché** (28% de V1). Causa desconocida: puede ser código o config distintos de los que se reconstruyeron (se usó la config de `c31cedc`; no hay versiones intermedias del 2026-08-04 al 2026-09-05) o la aproximación del caché (filas con timestamp <= t, sin verificar que no se reescriban).
- Por eso la reproducción cubre 144 de 189 órdenes y **no alcanza para afirmar cuánto cambia el PnL**.

**Problema de diseño que surge de esto.** `strategy_v1_sniper.py` detecta la señal en la vela donde `low <= entrada <= high` (variable `fill_pos`), y esa vela puede ser la que está en curso. Si el caché y el DataFrame solo tienen velas cerradas, esa señal llega hasta una vela más tarde (hasta 15 minutos en V1) o no llega. Aplicar los criterios 1 y 2 tal cual podría cambiar cuándo el bot ve las señales, no solo con qué valores. Hay que decidir el diseño antes de construir:

- **Opción A (hipótesis, el menor cambio de comportamiento):** persistir solo velas cerradas en `data/live/`, y que cada ciclo le pase a la estrategia las cerradas más la vela en curso leída de la API en ese momento, **solo en memoria, nunca guardada**. Se conserva el momento de detección y se evita que un valor parcial quede grabado para siempre.
- **Opción B:** todo cerrado (criterios 1 y 2 como están). Señales más limpias pero más tardías, y distintas de lo que vio el bot hasta ahora.

La elección depende de dos cosas que faltan medir: el test de la reproducción incluyendo la vela de entrada con su apertura (sin valores de cierre), y la causa de las 45 órdenes que no se reproducen.

## Resumen para Andrés

- **Qué pasa hoy:** el bot guarda en `data/live/` la vela que está en curso en el momento de consultar. En el ciclo siguiente la salta (pide solo velas posteriores a la última guardada), así que esa vela queda para siempre con sus valores parciales: volumen mucho menor y cierre distinto al real. Medimos que desde principios de agosto afecta del 28 al 37% de las horas de cripto, y que 188 de las 189 órdenes reales (4-ago a 2-oct) tuvieron al menos una hora afectada en las 24 horas previas en el activo que las originó.
- **Por qué importa:** el bot calcula sus señales desde esa caché (`run_live_trading.py`, V1 líneas ~332-333, V5 ~377-378, V10 ~404-405). Las señales de las últimas semanas pudieron calcularse con velas que no eran las reales. Esto puede explicar parte de la distancia entre el PF 1,13 real y el 2,00 del backtest. No está probado: lo mide la reproducción de señales.
- **Qué se construye:** (1) la caché solo guarda velas cerradas, (2) cada ciclo vuelve a pedir las últimas velas y la versión cerrada reemplaza a la parcial, (3) un script aparte, con simulacro, que repara las velas parciales ya guardadas usando la API.
- **Qué queda afuera:** cambios de la lógica de las estrategias, de ventanas, de riesgo o de apalancamiento; los datos del backtest (la instantánea ya usa la API); el diario sombra.
- **Riesgo:** **medio-alto**, porque cambia el código del bot en vivo y, con eso, las señales que va a generar. Por eso va en una rama aparte, con tests, un simulacro sobre una copia de la caché y tu confirmación antes del merge. Se revierte con `git revert`.
- **Decisiones tuyas:** cuándo desplegarlo (después de ver la reproducción) y si se repara la caché existente.

## Objetivo

Que toda señal del bot en vivo se calcule solo con velas cerradas y con los mismos valores que devuelve la API para esas velas.

## Causa (verificada en el código)

`src/live_data.py::update_live_data` calcula `since_ms = max(timestamp) + 1` y pide a partir de ahí. `fetch_data.py::fetch_ohlcv_paginated` devuelve lo que entrega el exchange, que puede incluir la vela en curso (no la filtra). La vela parcial se guarda y, como las siguientes consultas empiezan después de ella, nunca se vuelve a pedir. Además, el `drop_duplicates(subset="timestamp")` conserva la primera aparición, así que aunque se re-pidiera, ganaría la versión parcial.

Lo que no está confirmado: que la API devuelva la vela en curso. Se infiere del código y de la firma medida (volumen 88-95% menor, cierre distinto). El Tester lo comprueba con una consulta en vivo de solo lectura.

## Fuera de alcance

- Cambiar `fetch_data.py` para el uso offline (descargas históricas); si necesita el mismo filtro se evalúa aparte.
- Reconstruir los 15m anteriores al 2026-06-30 (la API no los devuelve; ya se validó que el tramo de noviembre a mayo coincide con la API en 1h).
- Cambiar qué señales se consideran válidas o la hora de entrada.
- El PnL real de las 189 órdenes (sale del export de BingX).

## Criterios de aceptación

1. **(Condicional a la opción elegida; ver Hallazgo.)** `update_live_data(exchange, symbol, timeframe, now_ms=None)` **guarda en disco** solo velas **cerradas**: una vela con apertura `t` está cerrada si `t + duración_del_timeframe <= now_ms`. El parámetro `now_ms` existe para poder probarlo con un reloj controlado; por defecto usa la hora actual UTC.
2. **(Condicional.)** La vela en curso no se escribe en la caché. Con la opción B tampoco está en el DataFrame devuelto; con la opción A se devuelve aparte y solo en memoria. En ambos casos se registra en el log cuántas velas parciales se descartaron o se mantuvieron en memoria.
3. **Re-pedido con solapamiento:** cada ciclo pide desde `max(timestamp) - K × duración` (con K = 3) y, ante un mismo `timestamp`, **gana la versión nueva** (no la primera). Una vela parcial ya guardada se reemplaza por su versión cerrada.
4. Idempotente: ejecutar `update_live_data` dos veces seguidas con los mismos datos de la API deja la caché idéntica.
5. Se conserva todo lo que ya hace el módulo: recuperación desde el original si el CSV está vacío o corrupto, y escritura atómica con archivo temporal y `os.replace`.
6. **Reparación de la caché existente:** un script aparte, `reparar_cache_velas.py`, con **simulacro por defecto** (no escribe) y una opción explícita para aplicar. Para cada archivo de `data/live/`: compara contra la API las velas desde el 2026-08-01, reemplaza las que difieren más de 0,01% en OHLC o más de 1% en volumen, y informa cuántas cambió por activo y timeframe. Antes de aplicar, hace una copia de seguridad de `data/live/` en una carpeta fuera del repo. No borra velas ni toca las anteriores al 2026-08-01.
7. Si la API no devuelve una vela que la caché tiene parcial, el script la marca en el informe y no la borra.
8. Los tests del bot que existen (`tests/`) siguen pasando. El Tester agrega tests con un exchange falso: (a) la vela en curso se descarta; (b) una parcial guardada se reemplaza por la cerrada; (c) idempotencia; (d) CSV corrupto sigue recuperándose; (e) el filtro funciona en 15m, 1h y 4h; (f) el script de reparación en modo simulacro no escribe nada y en modo aplicar cambia solo las velas que difieren.
9. **Simulacro sobre una copia:** antes del merge, el Constructor corre el código nuevo contra una copia de la caché actual y muestra cuántas señales del último ciclo cambian respecto del código viejo. Es informativo, no bloquea.
10. **Equivalencia de momento de señal (nuevo):** el Tester agrega un test que fija con un exchange falso que, con la opción elegida, una señal de V1 cuyo toque ocurre en la vela en curso se detecta en el mismo ciclo (opción A) o se documenta explícitamente el retraso (opción B).
11. **Nota en el diario y en el análisis:** `docs/` anota la fecha del despliegue, porque desde ese día las señales en vivo usan velas cerradas y los datos reales antes y después no son comparables sin esa marca.

## Diseño

- Cambio acotado a `src/live_data.py`. El filtro de velas cerradas y el re-pedido con solapamiento viven ahí, sin tocar `run_live_trading.py` ni las estrategias.
- La duración del timeframe sale de una tabla `{ "15m": 900000, "1h": 3600000, "4h": 14400000 }` (en milisegundos).
- Para el re-pedido, la fusión usa `concat` y `drop_duplicates(subset="timestamp", keep="last")` con el DataFrame nuevo al final.
- Sin dependencias nuevas, sin cambios de configuración.

## Seguridad y datos

- No se suben claves ni datos al repo. `data/` sigue ignorado y los informes del script van fuera del repo.
- El script de reparación no usa claves de API (solo velas públicas).
- No se toca el bot en vivo hasta que Andrés confirme el despliegue.

## Riesgo

**Medio-alto.** Cambia las señales del bot en vivo. Mitigaciones: simulacro sobre copia (criterio 9), copia de seguridad antes de reparar (criterio 6), rama aparte con tests y revert disponible.

## Recorrido

**Completo para el bot en vivo, liviano en lo demás.** El Tester escribe primero los tests del criterio 8 (rojos antes de construir). El Constructor implementa. `/revisar` verifica que no cambió nada fuera de `src/live_data.py` y del script nuevo. Andrés aprueba el despliegue.

## Orden

1. ~~Resultado de la reproducción de señales para las 189 órdenes.~~ Hecho (ver Hallazgo): insuficiente para decidir.
2. Pendiente de Claude Code, solo lectura: (a) repetir la reproducción incluyendo la vela de entrada con su apertura y sin valores de cierre; (b) buscar la causa de las 45 órdenes de V1 no reproducibles o, al menos, verificar si las filas del caché se reescriben después de guardarse.
3. Con ese resultado, se cierra el diseño (A o B) y Andrés decide si se construye y cuándo desplegar.
4. Tester, Constructor, revisión, simulacro, merge y `git pull` en la carpeta del bot.
5. Reparación de la caché (simulacro, luego aplicar), con el bot detenido o en un ciclo sin operar.

## Checklist del planificador

- [x] Cada criterio se puede probar con un test o tiene prueba manual escrita.
- [x] Lo que no se hace está en "Fuera de alcance".
- [x] Sin claves en la spec.
- [ ] Pendiente: confirmar que la API devuelve la vela en curso (primer test del Tester).
- [ ] Pendiente: cerrar el diseño A/B y la causa de las 45 órdenes no reproducibles.
