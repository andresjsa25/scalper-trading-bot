# Estado: caché de velas cerradas del bot en vivo

Fase actual: spec v2 (borrador). Reproducción de señales recibida pero insuficiente; diseño A/B sin cerrar. No construir.

## Registro

- 2026-10-04 · sesión principal (Claude) · Spec escrita a partir del diagnóstico de Claude Code: las señales salen de `data/live/`, la vela en curso se guarda parcial y nunca se reescribe. 189 órdenes reales (4-ago a 2-oct) con horas afectadas en las 24 h previas; la reproducción de señales dirá cuántas cambiaron de verdad.

- 2026-10-04 · sesión principal (Claude) · Spec v2 tras la reproducción de las 189 órdenes: entre los 58 casos comparables, 21 cambian de señal; 45 órdenes de V1 no se reproducen ni con el caché; y V1 detecta el toque en la vela en curso, así que "solo cerradas" puede retrasar señales. Criterios 1-2 pasan a condicionales; se agrega criterio 10 (equivalencia de momento). Pendiente de Claude Code: reproducción con la apertura de la vela de entrada y causa de las 45.
