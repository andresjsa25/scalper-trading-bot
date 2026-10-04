# Estudio de eventos: frecuencia (fase 0)

Generado el 2026-10-04 con `python -m estudio_eventos.fase0`. Solo conteos de eventos deduplicados (8 velas). Ninguna columna de resultado de precio. Fuente: `data/backtest_snapshot/` (1h y 4h; el diario se arma desde 1h). Universo principal = cripto, HYPE, XAUT, SOL (datos desde 2025). Universo secundario = NC* (solo C1 y C2, reportado aparte).

Regla: celdas con menos de 30 eventos en E (universo principal) se marcan como **no evaluable**.

## Tabla 1: conteo por hipotesis, version, temporalidad y sentido

| hipotesis | version | tf | sentido | prin_E | prin_C1 | prin_C2 | sec_C1 | sec_C2 | evaluable |
|---|---|---|---|---|---|---|---|---|---|
| H1 | completa | 1h | long | 1 | 3 | 1 | 1 | 2 | no evaluable |
| H1 | completa | 1h | short | 1 | 0 | 3 | 2 | 1 | no evaluable |
| H1 | completa | 4h | long | 1 | 0 | 0 | 0 | 0 | no evaluable |
| H1 | completa | 4h | short | 1 | 0 | 0 | 0 | 2 | no evaluable |
| H1 | con_estructura_mayor | 1h | long | 1 | 1 | 1 | 0 | 1 | no evaluable |
| H1 | con_estructura_mayor | 1h | short | 0 | 0 | 1 | 1 | 1 | no evaluable |
| H1 | con_estructura_mayor | 4h | short | 0 | 0 | 0 | 0 | 2 | no evaluable |
| H1 | sin_fvg | 1h | long | 140 | 186 | 173 | 62 | 206 | si |
| H1 | sin_fvg | 1h | short | 168 | 210 | 205 | 69 | 235 | si |
| H1 | sin_fvg | 4h | long | 40 | 60 | 42 | 16 | 54 | si |
| H1 | sin_fvg | 4h | short | 53 | 62 | 57 | 10 | 78 | si |
| H1 | sin_rechazo | 1h | long | 13 | 25 | 22 | 12 | 32 | no evaluable |
| H1 | sin_rechazo | 1h | short | 18 | 16 | 28 | 19 | 36 | no evaluable |
| H1 | sin_rechazo | 4h | long | 2 | 2 | 2 | 4 | 8 | no evaluable |
| H1 | sin_rechazo | 4h | short | 3 | 6 | 6 | 0 | 12 | no evaluable |
| H2 | completa | 1h | long | 11 | 24 | 17 | 6 | 15 | no evaluable |
| H2 | completa | 1h | short | 15 | 20 | 18 | 0 | 4 | no evaluable |
| H2 | completa | 4h | long | 2 | 5 | 5 | 0 | 0 | no evaluable |
| H2 | completa | 4h | short | 2 | 2 | 3 | 0 | 1 | no evaluable |
| H2 | sin_adx | 1h | long | 45 | 62 | 51 | 12 | 38 | si |
| H2 | sin_adx | 1h | short | 37 | 53 | 59 | 1 | 19 | si |
| H2 | sin_adx | 4h | long | 9 | 17 | 16 | 1 | 6 | no evaluable |
| H2 | sin_adx | 4h | short | 6 | 11 | 16 | 2 | 5 | no evaluable |
| H2 | sin_fvg | 1h | long | 188 | 266 | 221 | 24 | 125 | si |
| H2 | sin_fvg | 1h | short | 204 | 259 | 236 | 27 | 136 | si |
| H2 | sin_fvg | 4h | long | 42 | 39 | 49 | 3 | 29 | si |
| H2 | sin_fvg | 4h | short | 37 | 52 | 58 | 10 | 32 | si |
| H2 | sin_volumen | 1h | long | 30 | 43 | 33 | 12 | 46 | si |
| H2 | sin_volumen | 1h | short | 32 | 35 | 41 | 7 | 35 | si |
| H2 | sin_volumen | 4h | long | 5 | 6 | 7 | 3 | 5 | no evaluable |
| H2 | sin_volumen | 4h | short | 10 | 6 | 7 | 2 | 4 | no evaluable |
| H3 | completa | 1h | long | 3 | 0 | 2 | 0 | 3 | no evaluable |
| H3 | completa | 1h | short | 3 | 4 | 5 | 0 | 3 | no evaluable |
| H3 | completa | 4h | long | 0 | 1 | 1 | 0 | 1 | no evaluable |
| H3 | completa | 4h | short | 0 | 0 | 0 | 0 | 1 | no evaluable |
| H3 | sin_fibonacci | 1h | long | 71 | 89 | 75 | 12 | 63 | si |
| H3 | sin_fibonacci | 1h | short | 58 | 82 | 76 | 6 | 39 | si |
| H3 | sin_fibonacci | 4h | long | 12 | 25 | 21 | 1 | 15 | no evaluable |
| H3 | sin_fibonacci | 4h | short | 22 | 13 | 23 | 3 | 15 | no evaluable |
| H3 | sin_fvg | 1h | long | 21 | 26 | 25 | 2 | 24 | no evaluable |
| H3 | sin_fvg | 1h | short | 29 | 28 | 30 | 1 | 17 | no evaluable |
| H3 | sin_fvg | 4h | long | 4 | 9 | 4 | 0 | 3 | no evaluable |
| H3 | sin_fvg | 4h | short | 9 | 4 | 7 | 1 | 10 | no evaluable |
| H3 | sin_volumen | 1h | long | 8 | 9 | 9 | 1 | 16 | no evaluable |
| H3 | sin_volumen | 1h | short | 13 | 11 | 14 | 4 | 11 | no evaluable |
| H3 | sin_volumen | 4h | long | 2 | 5 | 3 | 1 | 5 | no evaluable |
| H3 | sin_volumen | 4h | short | 2 | 1 | 1 | 0 | 4 | no evaluable |
| H4 | completa | 1h | long | 109 | 167 | 179 | 15 | 84 | si |
| H4 | completa | 1h | short | 135 | 179 | 140 | 8 | 58 | si |
| H4 | completa | 4h | long | 27 | 43 | 46 | 3 | 31 | no evaluable |
| H4 | completa | 4h | short | 36 | 49 | 47 | 3 | 30 | si |
| H4 | compresion_1_vela | 1h | long | 215 | 301 | 322 | 37 | 154 | si |
| H4 | compresion_1_vela | 1h | short | 275 | 323 | 285 | 23 | 111 | si |
| H4 | compresion_1_vela | 4h | long | 47 | 91 | 81 | 5 | 59 | si |
| H4 | compresion_1_vela | 4h | short | 65 | 88 | 81 | 7 | 53 | si |
| H4 | sin_volumen | 1h | long | 257 | 288 | 295 | 77 | 254 | si |
| H4 | sin_volumen | 1h | short | 287 | 258 | 240 | 57 | 178 | si |
| H4 | sin_volumen | 4h | long | 68 | 59 | 90 | 14 | 74 | si |
| H4 | sin_volumen | 4h | short | 65 | 76 | 92 | 14 | 79 | si |
| H5 | base | 1h | long | 261 | 283 | 306 | 96 | 334 | si |
| H5 | base | 1h | short | 272 | 260 | 292 | 91 | 330 | si |
| H5 | base | 4h | long | 69 | 66 | 67 | 27 | 75 | si |
| H5 | base | 4h | short | 77 | 72 | 69 | 27 | 68 | si |
| H5 | base_ambos | 1h | long | 49 | 68 | 68 | 4 | 46 | si |
| H5 | base_ambos | 1h | short | 59 | 76 | 58 | 5 | 42 | si |
| H5 | base_ambos | 4h | long | 9 | 14 | 17 | 3 | 9 | no evaluable |
| H5 | base_ambos | 4h | short | 15 | 16 | 15 | 4 | 13 | no evaluable |
| H5 | base_fvg_ruptura | 1h | long | 179 | 174 | 200 | 46 | 198 | si |
| H5 | base_fvg_ruptura | 1h | short | 193 | 178 | 202 | 54 | 177 | si |
| H5 | base_fvg_ruptura | 4h | long | 44 | 38 | 41 | 22 | 43 | si |
| H5 | base_fvg_ruptura | 4h | short | 54 | 51 | 44 | 25 | 36 | si |
| H5 | base_volumen_barrida | 1h | long | 79 | 127 | 111 | 12 | 68 | si |
| H5 | base_volumen_barrida | 1h | short | 99 | 123 | 99 | 14 | 78 | si |
| H5 | base_volumen_barrida | 4h | long | 20 | 29 | 27 | 4 | 17 | no evaluable |
| H5 | base_volumen_barrida | 4h | short | 26 | 24 | 19 | 4 | 21 | no evaluable |

## Tabla 2: principal, por simbolo y mes (solo versiones completas: H1-H4 `completa` y H5 `base`; suma de 1h/4h y sentidos)

| simbolo | 2025-01 | 2025-02 | 2025-03 | 2025-04 | 2025-05 | 2025-06 | 2025-07 | 2025-08 | 2025-09 | 2025-10 | 2025-11 | 2025-12 | 2026-01 | 2026-02 | 2026-03 | 2026-04 | 2026-05 | 2026-06 | 2026-07 | 2026-08 | 2026-09 | 2026-10 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ADA | 16 | 16 | 30 | 23 | 18 | 17 | 15 | 20 | 26 | 22 | 16 | 22 | 27 | 20 | 33 | 25 | 20 | 17 | 16 | 17 | 21 | 5 |
| BNB | 19 | 16 | 14 | 16 | 9 | 14 | 18 | 22 | 11 | 25 | 25 | 23 | 23 | 23 | 20 | 18 | 17 | 18 | 21 | 13 | 16 | 2 |
| BTC | 28 | 18 | 20 | 31 | 27 | 31 | 24 | 22 | 30 | 17 | 23 | 25 | 23 | 24 | 23 | 23 | 18 | 26 | 31 | 24 | 23 | 2 |
| ETH | 22 | 17 | 18 | 24 | 23 | 26 | 13 | 15 | 20 | 22 | 17 | 20 | 19 | 20 | 33 | 16 | 32 | 17 | 21 | 23 | 23 | 0 |
| HYPE | 25 | 23 | 24 | 18 | 18 | 22 | 18 | 17 | 19 | 24 | 23 | 20 | 21 | 18 | 26 | 22 | 25 | 26 | 19 | 30 | 17 | 2 |
| LINK | 24 | 25 | 16 | 20 | 18 | 25 | 17 | 26 | 19 | 20 | 23 | 31 | 22 | 17 | 25 | 21 | 23 | 20 | 18 | 16 | 13 | 2 |
| SOL | 15 | 11 | 16 | 27 | 18 | 17 | 16 | 24 | 18 | 28 | 15 | 32 | 17 | 14 | 21 | 24 | 20 | 23 | 13 | 26 | 20 | 2 |
| XAUT | 0 | 0 | 0 | 9 | 11 | 17 | 11 | 17 | 14 | 11 | 17 | 20 | 23 | 17 | 17 | 24 | 19 | 18 | 13 | 29 | 19 | 5 |

## Tabla 3: secundario NC* por bloque (solo versiones completas; no entra al criterio de fase 1)

| simbolo | C1 | C2 |
|---|---|---|
| NCCO1OILBRENT2USD | 0 | 120 |
| NCCOXAG2USD | 2 | 131 |
| NCSINASDAQ1002USD | 52 | 135 |
| NCSISP5002USD | 45 | 126 |
| NCSKAAPL2USD | 40 | 120 |
| NCSKAMZN2USD | 43 | 100 |
| NCSKGOOGL2USD | 37 | 100 |
| NCSKMETA2USD | 29 | 118 |
| NCSKNVDA2USD | 31 | 93 |
