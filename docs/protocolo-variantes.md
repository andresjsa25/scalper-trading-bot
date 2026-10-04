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

- Datos: velas de 15m, 1h y 4h de `data/`, del **2025-11-23 al 2026-10-02**
  (313 días, unos 10 meses). El criterio de "una ventana de aproximadamente un
  año" se aplica sobre todo el historial disponible. No se estira ni se
  recorta.
- Tres períodos iguales (unos 104 días cada uno):
  - P1: 2025-11-23 a 2026-03-07
  - P2: 2026-03-08 a 2026-06-19
  - P3: 2026-06-20 a 2026-10-02
- Los períodos de `docs/analisis_ventanas_2026-10.md` (nov-mar, abr-jun,
  jul-oct) quedan solo como referencia histórica. No se usan para decidir.
- Los datos posteriores al 2026-10-02 **no entran al backtest**: son para el
  diario sombra (datos hacia adelante).

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
| V5-orig | V5 original, todos los activos (la que dio PF 0,87) |
| V5-alt1 | V5 con entrada en 4h y contexto diario |
| V5-alt2 | V5-alt1 con filtro de patrón de vela más estricto. **Definición exacta pendiente**: se escribe antes de la primera corrida y requiere el OK de Andrés |

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
| Comisión maker | 0,02% | _completar_ |
| Comisión taker | 0,05% | _completar_ |
| Deslizamiento por lado | 0,02% | _completar_ |
| Funding | _no modelado_ | _completar o justificar_ |

Se reportan R bruto y R neto en columnas separadas.

## 5. Simulación

- El mismo simulador para todas las variantes (el "pesimista" del análisis
  anterior): el stop se evalúa desde la vela del toque y, si una vela toca SL y
  TP, **gana el SL**.
- Sin look-ahead: una señal usa solo datos hasta el cierre de su vela.
- Órdenes límite (V1): se reporta aparte la **tasa de llenado simulada**. En
  vivo, las órdenes que se llenan tienden a ser las que siguen en contra, así
  que el backtest puede sobrestimar.
- Reglas de ejecución del bot (riesgo 1%, tope de 5 USD por trade, máximo 10
  operaciones, 30% de riesgo abierto, una posición por símbolo) se aplican
  igual que en vivo. Se reporta cuántas señales se descartan por esas reglas.

## 6. Qué se mide

Por variante: trades, R medio neto, PF neto, PF en P1, P2 y P3, drawdown máximo
en R, tasa de llenado (V1) y concentración por activo (porcentaje de trades de
los 3 activos principales). Los 16 activos no son 16 muestras independientes
(las cripto están correlacionadas).

Intervalo de confianza del PF: bootstrap **por día** (se remuestrean días, no
trades, por la correlación entre activos), 10.000 remuestreos, 95%.

## 7. Criterio de aceptación

Una variante sobrevive solo si cumple **todo**:

1. Al menos **100 trades** en todo el historial.
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

## 11. Historial del protocolo

| Versión | Fecha | Cambio |
|---|---|---|
| v1 | 2026-10-04 | Primera versión, borrador |
