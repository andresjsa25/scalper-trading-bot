# Spec: estudio de eventos de patrones (RSI, ADX, Bollinger, FVG, barridos, Fibonacci, volumen)

**Estado: borrador v1. NO SE EJECUTA.** Falta que Andrés lo apruebe. Este estudio es **investigación, no el protocolo v1**: no cambia las 9 variantes ni el tag `protocolo-v1`. Lo que sobreviva solo puede entrar a un `protocolo-v2`.

## Resumen para Andrés

- **Qué se hace:** se definen 5 hipótesis de patrón con reglas exactas (las tuyas: RSI sobrevendido + FVG + vela de rechazo + estructura de 4h; ADX + Bollinger + FVG + volumen; barrida de liquidez + volumen + Fibonacci + FVG; y dos agregadas: compresión de volatilidad y ruptura, y cambio de estructura tras una barrida). Se cuenta cada cuánto se dan y se mide qué hace el precio después, comparado con entradas al azar en los mismos activos y horarios.
- **Qué NO se hace:** no se busca "el punto más bajo o más alto" (solo se reconoce mirando hacia atrás). Se mide si, dado un patrón, el movimiento siguiente es mejor que el azar, ya descontando costos.
- **Cómo se evita engañarnos:** reglas y valores escritos antes de mirar resultados; los datos se dividen en 3 bloques (se explora en el primero, se confirma en los otros dos sin retocar); se cuenta cada prueba; el dato final es el diario forward.
- **Qué sale:** una tabla de frecuencia (fase 0, sin mirar resultados) y, después, qué patrones se sostienen y cuáles no. "Ninguno se sostiene" es un resultado válido.
- **Riesgo:** bajo. Es solo lectura sobre datos históricos; no toca el bot en vivo ni `data/`.
- **Decisiones tuyas:** aprobar las definiciones de la sección 3 y los valores de la sección 4; decidir si, con la fase 0 hecha, se pasa a la fase 1.

## Objetivo

Saber, con evidencia, si alguna combinación de condiciones de las tres hipótesis anticipa un movimiento a favor mejor que el azar, cada cuánto se da, y qué filtro (volumen, ADX, alineación de temporalidades) aporta de verdad.

## Qué queda afuera

- Cambiar el bot en vivo, sus ventanas, riesgo o apalancamiento.
- Cambiar las 9 variantes o los criterios del `docs/protocolo-variantes.md`.
- Optimizar parámetros. Los valores son estándar y fijos (sección 4).
- Armar reglas de stop/TP/gestión: eso es una etapa posterior (`protocolo-v2`).
- Cualquier decisión de capital real basada en este estudio.

## 1. Datos y bloques

- Velas de 1h y 4h de la instantánea `data/backtest_snapshot/` (la misma del protocolo v1, SHA en su manifiesto). El diario (1D) se arma remuestreando 1h en UTC. **No se usa 15m.**
- Cripto, HYPE, XAUT y SOL tienen 1h/4h desde 2025-01-01 (XAUT desde 2025-04-03, HYPE desde 2024-12-19). Los NC* (acciones, índices, commodities sintéticos) solo desde su listado (nov-2025 a mar-2026).
- Tres bloques de duración casi igual, por fecha de la vela de señal:

| Bloque | Desde | Hasta | Uso |
|---|---|---|---|
| E (exploración) | 2025-01-01 | 2025-08-01 | fases 0 y 1 |
| C1 (confirmación 1) | 2025-08-02 | 2026-03-02 | fase 2 |
| C2 (confirmación 2) | 2026-03-03 | 2026-10-02 | fase 2 |

- **Universo principal:** activos con datos en E (cripto, HYPE, XAUT, SOL). **Universo secundario:** NC*, que no existen en E; se evalúan solo en C1 y C2 y se reportan aparte, como confirmación fuera de muestra por activo.
- El volumen de los NC* (sintéticos de BingX) puede no ser confiable. Se incluyen igual, como pidió Andrés, y se reportan siempre separados de cripto para poder ver si el filtro de volumen se comporta distinto.
- **Honestidad sobre los datos:** V1/V5/V10 se calibraron y las confluencias V7/V8 se escanearon sobre parte de este historial. Ningún bloque es virgen. La prueba fuera de muestra de verdad es el diario forward.
- Un día con huecos en 1h no cuenta como día completo para el diario (regla del protocolo v1, sección 2).

## 2. Señales y ejecución teórica (sin mirar el futuro)

- Una condición se evalúa **al cierre de la vela de señal**; la entrada teórica es la **apertura de la vela siguiente**. Todo indicador en la vela *i* usa solo velas ≤ *i*.
- **Pivotes (swings):** un máximo o mínimo local con n = 3 velas a cada lado. Un pivote solo existe a partir de 3 velas después de formarse. Se usan solo pivotes ya confirmados.
- Cada hipótesis se evalúa en **long y en short** (reglas espejo), en **1h y 4h**.
- **Deduplicación:** tras un evento en un símbolo, sentido y temporalidad, no se cuenta otro hasta 8 velas después.

## 3. Definiciones exactas

Indicadores (valores estándar, sección 4): RSI de Wilder, ADX de Wilder, Bollinger sobre SMA, ATR de Wilder.

- **Volumen alto:** volumen de la vela ≥ 1,5 × media de las 20 velas anteriores.
- **FVG alcista:** en la vela *i*, `low[i] > high[i-2]`; zona = [`high[i-2]`, `low[i]`]. Espejo para bajista. **Sin rellenar** mientras ninguna vela posterior haya operado dentro de la zona. **Vigente:** formado en las últimas 24 velas. **Tocado:** la vela de señal opera dentro de la zona. Al construir, el Tester compara con el detector de `src/strategy_v1_sniper.py` y documenta cualquier diferencia antes de la primera corrida.
- **Vela de rechazo (long):** martillo (mecha inferior ≥ 2 × cuerpo y cierre en la mitad superior del rango) **o** envolvente alcista (vela previa bajista; apertura < cierre previo y cierre > apertura previa). Espejo para short.
- **Estructura mayor alineada (long):** el último mínimo confirmado de la temporalidad mayor es más alto que el anterior (4h para señales de 1h; diario para señales de 4h). Espejo para short con máximos.
- **Barrida de liquidez (long):** la vela hace `low` por debajo del último pivote mínimo confirmado y **cierra por encima** de ese pivote. Espejo para short.
- **Zona de Fibonacci (long):** con el último tramo alcista confirmado (pivote mínimo L → pivote máximo H, R = H − L), la zona es [H − 0,618·R, H − 0,5·R]. La vela de barrida cierra dentro de esa zona. Espejo para short.

### Hipótesis

| ID | Long (el short es el espejo) |
|---|---|
| H1 | RSI < 30 + FVG alcista vigente, sin rellenar y tocado + vela de rechazo (+ filtro opcional: estructura mayor alineada) |
| H2 | ADX < 20 + `low` ≤ banda inferior de Bollinger y cierre por encima de ella + FVG alcista vigente, sin rellenar y tocado + volumen alto |
| H3 | Barrida de liquidez + volumen alto + cierre en la zona de Fibonacci + FVG alcista vigente y sin rellenar |
| H4 | Compresión y expansión: ancho de Bollinger en el percentil ≤ 20 de sus últimas 100 velas durante al menos 6 velas consecutivas, y la vela de señal **cierra por encima del máximo** de esas velas de compresión con volumen alto |
| H5 | Cambio de estructura tras una barrida: barrida de liquidez en la vela S; la señal es la primera vela, dentro de las 12 siguientes a S, que **cierra por encima del último pivote máximo confirmado antes de S**, sin que ninguna vela entre S y ella haya hecho un `low` menor al de S |

Ancho de Bollinger = (banda superior − banda inferior) / SMA(20). En H4 y H5 el evento es la vela de ruptura, no la de compresión ni la de barrida. En H4 la compresión se mide con las velas **previas** a la señal. El short es el espejo (cierre por debajo del mínimo de la compresión; cierre por debajo del último pivote mínimo confirmado antes de S, sin `high` mayor al de S).

Versiones evaluadas por hipótesis (para ver qué aporta cada filtro):
- **H1:** completa (sin estructura mayor), con estructura mayor alineada, sin rechazo, sin FVG.
- **H2:** completa, sin ADX, sin volumen, sin FVG.
- **H3:** completa, sin volumen, sin Fibonacci, sin FVG.
- **H4:** completa, sin volumen, con compresión de solo 1 vela (sin la duración mínima).
- **H5:** base (barrida + ruptura), base + volumen alto en la barrida, base + FVG alcista formado durante la ruptura, base + ambos.

## 4. Valores fijos (no se ajustan)

RSI 14 (sobrevendido < 30, sobrecomprado > 70) · ADX 14 (lateral < 20) · Bollinger 20 periodos, 2 desviaciones · ATR 14 · volumen alto ≥ 1,5× media 20 · pivote n = 3 · FVG vigente 24 velas · compresión: percentil ≤ 20 del ancho de Bollinger en 100 velas, mínimo 6 velas seguidas (H4) · ventana de ruptura 12 velas (H5) · deduplicación 8 velas · horizonte principal **8 velas** (sensibilidad: 4 y 16, solo descriptivas) · costo base de ida y vuelta según la sección 4 del protocolo v1 (sensibilidad con el costo bajo y alto que ese documento define).

Una ambigüedad de una definición se resuelve **antes de la primera corrida y sin mirar resultados**, y se deja anotada en `estado.md`.

## 5. Qué se mide

Por evento: retorno en el sentido de la operación desde la apertura siguiente hasta el cierre a +8 velas, **neto de costos y expresado en unidades de ATR(14) de la vela de señal**; además, el movimiento máximo a favor y el máximo en contra dentro de las 8 velas (descriptivo).

**Referencia al azar:** para cada evento, 20 velas al azar del mismo símbolo, temporalidad, sentido, **bloque y hora del día**, excluyendo velas con un evento. Se mide la diferencia evento − promedio de su referencia. Semilla fija.

**Intervalo:** bootstrap por día (re-muestreo de días), 95%, sobre la diferencia media.

**Frecuencia (fase 0):** eventos por símbolo y por mes, por hipótesis, versión, temporalidad y sentido, en los tres bloques. No incluye ningún resultado de precio.

## 6. Fases y criterios

- **Fase 0 (frecuencia):** solo conteos. Si una celda tiene menos de 30 eventos en E, se descarta como no evaluable y se anota.
- **Fase 1 (exploración, bloque E, universo principal):** una celda "pasa" si tiene ≥ 30 eventos y la cota inferior del intervalo de la diferencia es > 0.
- **Fase 2 (confirmación, C1 y C2, solo las celdas que pasaron):** se confirma si, en C1 **y** C2 por separado, la diferencia tiene el mismo signo y al menos la mitad de la magnitud de E, y en C1 + C2 juntos la cota inferior del intervalo (con corrección de Bonferroni sobre el número de celdas que pasaron la fase 1) es > 0. Los NC* se reportan aparte, sin entrar al criterio.
- **Un patrón "que sirve"** es el que se confirma y además mantiene la diferencia positiva con el costo alto. Eso no lo convierte en estrategia: solo lo habilita para escribir una variante en `protocolo-v2` y pasar al diario forward.

## 7. Registro de pruebas

`docs/estudio-eventos-registro.md`, solo agregar (nunca editar lo escrito): cada celda evaluada, en qué fase y con qué resultado, aunque no pase. El **N máximo declarado** es 5 hipótesis × 2 sentidos × 2 temporalidades × hasta 5 versiones = 100 celdas (las versiones reales suman 4 + 4 + 4 + 3 + 4 = 19 por sentido y temporalidad, o sea 76 celdas). **No se agregan hipótesis a esta ronda después de aprobar la spec**: una hipótesis nueva es una ronda 2 con su propio conteo, y se cuenta contra la misma corrección. Las pruebas previas de confluencias (V7/V8, `research_indicator_confluence_scan.py`) se anotan como contexto, sin números.

## Criterios de aceptación

1. Existe `docs/estudio-eventos-registro.md` y toda celda evaluada figura en él.
2. Las definiciones de la sección 3 están implementadas tal cual y hay un test por cada una, con datos sintéticos.
3. Un test demuestra que ningún indicador ni evento usa información posterior a la vela de señal (truncar el futuro no cambia la señal).
4. Un test cubre la deduplicación de 8 velas y la referencia al azar (misma hora, sentido y bloque; excluye eventos).
5. El bootstrap por día es reproducible (semilla fija) y su resultado se repite idéntico.
6. La fase 0 produce la tabla de frecuencia sin ninguna columna de resultados de precio.
7. Las fases 1 y 2 no se ejecutan hasta que Andrés apruebe la salida de la fase 0.
8. El resumen final separa cripto y NC*, e informa también los patrones que no se confirmaron.
9. No se toca `run_live_trading.py`, `src/` del bot en vivo, `data/` ni el protocolo v1; los datos y los listados de eventos crudos no se suben al repo (solo tablas resumen).
10. Los tests existentes del proyecto (`pytest`) siguen en verde.

## Orden de trabajo

1. Andrés aprueba esta spec (merge del PR).
2. Tester escribe los tests (criterios 2–5) y confirma que fallan por la razón correcta.
3. Constructor implementa en rama aparte; `/revisar`.
4. Se corre la fase 0 y se muestra la tabla de frecuencia.
5. Con el OK de Andrés, fase 1; con otro OK, fase 2.
6. Lo que se confirme se escribe como variante en `protocolo-v2` (spec aparte).

## Anexo 2026-10-04: decisiones de Andrés

Estas decisiones prevalecen sobre el texto original de las secciones 2 y 3 donde difieran. No cambian las hipótesis ni las versiones.

- **Vigencia del FVG (§3):** formado en j con i-23 ≤ j ≤ i, es decir, las 24 velas que incluyen la vela de señal.
- **Relleno del FVG (§3):** una vela rellena solo si cruza el interior de la zona (contacto solo en el borde no cuenta). El relleno revisa las velas j+1..i-1; la vela de señal no cuenta como relleno (decisión sobre H3).
- **Toque de la señal (§3):** estricto, la vela de señal cruza el interior de la zona.
- **Deduplicación (§2):** un evento contado bloquea i+1..i+7; un evento en i+8 cuenta. Los eventos suprimidos no bloquean (el bloqueo se mide desde el último evento contado).
- **Diferencia (§5):** el estadístico del bootstrap por día es la media de la diferencia evento − referencia al azar, con semilla fija.
- **Universo principal (§1, §6):** XAUT queda en el universo principal con cobertura parcial en E (desde 2025-04-03), decisión de Andrés.
- **Unidad de celda (§7, 76 celdas):** celda = hipótesis × sentido × temporalidad × bloque, con todos los símbolos juntos. El detalle por símbolo es descriptivo y sin test. Decisión de Andrés. Pendiente de implementar antes de fase 1 (el resumen de este PR todavía agrupa por símbolo).
- **Exclusión de candidatas al azar (§5):** la referencia excluye solo las velas de la celda, no las de todas las hipótesis. Decisión de Andrés.
- **Eventos suprimidos (§2, §5):** solo cuentan los eventos contados; las velas de eventos suprimidos por dedup pueden ser candidatas de la referencia. Decisión de Andrés.

### Corrección 2026-10-04: unidad de celda (reemplaza la entrada de arriba, que queda como registro)

- **Celda:** hipótesis-versión × temporalidad × sentido. Son 76 celdas, como declara §7. Todos los símbolos van juntos dentro de cada celda.
- **Bloques y costos:** bloques E, C1 y C2 y costos (base 0,11 %; sensibilidades 0,08 % y 0,14 %) son columnas dentro de la celda, no filas.
- **Máximos:** MFE y MAE brutos, sin costos, en unidades de ATR(14) de la vela de señal, horizonte i+1..i+8.
- **Exclusión de candidatas al azar:** solo las velas de la celda; y solo cuentan los eventos contados.
- **Detalle por símbolo:** descriptivo, sin cotas ni significancia.

- **Cierre 2026-10-05:** fase 1 corrida sobre E (76 celdas): 0 pasan, 39 no pasan, 37 no evaluables. C1 y C2 sin tocar; fase 2 no ejecutada. Estudio cerrado, sin reabrir (ver `estado.md`).
