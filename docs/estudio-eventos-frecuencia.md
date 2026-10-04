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
| H1 | con_estructura_mayor | 4h | long | 0 | 0 | 0 | 0 | 0 | no evaluable |
| H1 | con_estructura_mayor | 4h | short | 0 | 0 | 0 | 0 | 2 | no evaluable |
| H1 | sin_fvg | 1h | long | 140 | 186 | 173 | 62 | 206 | si |
| H1 | sin_fvg | 1h | short | 168 | 210 | 205 | 69 | 235 | si |
| H1 | sin_fvg | 4h | long | 40 | 60 | 42 | 16 | 54 | si |
| H1 | sin_fvg | 4h | short | 53 | 62 | 57 | 10 | 78 | si |
| H1 | sin_rechazo | 1h | long | 13 | 25 | 23 | 12 | 34 | no evaluable |
| H1 | sin_rechazo | 1h | short | 18 | 16 | 28 | 21 | 37 | no evaluable |
| H1 | sin_rechazo | 4h | long | 2 | 2 | 2 | 4 | 8 | no evaluable |
| H1 | sin_rechazo | 4h | short | 3 | 6 | 6 | 0 | 12 | no evaluable |
| H2 | completa | 1h | long | 11 | 24 | 17 | 6 | 15 | no evaluable |
| H2 | completa | 1h | short | 15 | 21 | 19 | 0 | 4 | no evaluable |
| H2 | completa | 4h | long | 2 | 5 | 5 | 0 | 0 | no evaluable |
| H2 | completa | 4h | short | 2 | 2 | 3 | 0 | 1 | no evaluable |
| H2 | sin_adx | 1h | long | 45 | 62 | 51 | 12 | 39 | si |
| H2 | sin_adx | 1h | short | 37 | 54 | 61 | 1 | 20 | si |
| H2 | sin_adx | 4h | long | 9 | 17 | 17 | 1 | 6 | no evaluable |
| H2 | sin_adx | 4h | short | 6 | 11 | 16 | 2 | 5 | no evaluable |
| H2 | sin_fvg | 1h | long | 188 | 266 | 221 | 24 | 125 | si |
| H2 | sin_fvg | 1h | short | 204 | 259 | 236 | 27 | 136 | si |
| H2 | sin_fvg | 4h | long | 42 | 39 | 49 | 3 | 29 | si |
| H2 | sin_fvg | 4h | short | 37 | 52 | 58 | 10 | 32 | si |
| H2 | sin_volumen | 1h | long | 31 | 45 | 38 | 12 | 46 | si |
| H2 | sin_volumen | 1h | short | 32 | 39 | 42 | 7 | 36 | si |
| H2 | sin_volumen | 4h | long | 5 | 6 | 7 | 3 | 5 | no evaluable |
| H2 | sin_volumen | 4h | short | 10 | 6 | 7 | 2 | 4 | no evaluable |
| H3 | completa | 1h | long | 3 | 0 | 2 | 0 | 3 | no evaluable |
| H3 | completa | 1h | short | 3 | 4 | 5 | 0 | 3 | no evaluable |
| H3 | completa | 4h | long | 0 | 1 | 1 | 0 | 1 | no evaluable |
| H3 | completa | 4h | short | 0 | 0 | 0 | 0 | 1 | no evaluable |
| H3 | sin_fibonacci | 1h | long | 71 | 90 | 76 | 12 | 64 | si |
| H3 | sin_fibonacci | 1h | short | 58 | 84 | 77 | 6 | 40 | si |
| H3 | sin_fibonacci | 4h | long | 12 | 25 | 22 | 1 | 15 | no evaluable |
| H3 | sin_fibonacci | 4h | short | 22 | 13 | 23 | 3 | 15 | no evaluable |
| H3 | sin_fvg | 1h | long | 21 | 26 | 25 | 2 | 24 | no evaluable |
| H3 | sin_fvg | 1h | short | 29 | 28 | 30 | 1 | 17 | no evaluable |
| H3 | sin_fvg | 4h | long | 4 | 9 | 4 | 0 | 3 | no evaluable |
| H3 | sin_fvg | 4h | short | 9 | 4 | 7 | 1 | 10 | no evaluable |
| H3 | sin_volumen | 1h | long | 8 | 9 | 9 | 2 | 16 | no evaluable |
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
| H5 | base | 1h | long | 352 | 401 | 416 | 141 | 463 | si |
| H5 | base | 1h | short | 376 | 375 | 399 | 140 | 475 | si |
| H5 | base | 4h | long | 101 | 89 | 99 | 33 | 98 | si |
| H5 | base | 4h | short | 103 | 98 | 101 | 39 | 104 | si |
| H5 | base_ambos | 1h | long | 72 | 106 | 104 | 6 | 63 | si |
| H5 | base_ambos | 1h | short | 94 | 123 | 98 | 12 | 74 | si |
| H5 | base_ambos | 4h | long | 17 | 24 | 26 | 5 | 15 | no evaluable |
| H5 | base_ambos | 4h | short | 23 | 24 | 23 | 8 | 26 | no evaluable |
| H5 | base_fvg_ruptura | 1h | long | 245 | 270 | 288 | 69 | 284 | si |
| H5 | base_fvg_ruptura | 1h | short | 273 | 270 | 287 | 95 | 294 | si |
| H5 | base_fvg_ruptura | 4h | long | 70 | 58 | 66 | 27 | 61 | si |
| H5 | base_fvg_ruptura | 4h | short | 74 | 74 | 71 | 35 | 66 | si |
| H5 | base_volumen_barrida | 1h | long | 114 | 180 | 161 | 21 | 101 | si |
| H5 | base_volumen_barrida | 1h | short | 140 | 176 | 154 | 22 | 123 | si |
| H5 | base_volumen_barrida | 4h | long | 32 | 39 | 40 | 7 | 23 | si |
| H5 | base_volumen_barrida | 4h | short | 38 | 34 | 31 | 8 | 38 | si |

## Tabla 2: principal, por simbolo y mes (solo versiones completas: H1-H4 `completa` y H5 `base`; suma de 1h/4h y sentidos)

| simbolo | 2025-01 | 2025-02 | 2025-03 | 2025-04 | 2025-05 | 2025-06 | 2025-07 | 2025-08 | 2025-09 | 2025-10 | 2025-11 | 2025-12 | 2026-01 | 2026-02 | 2026-03 | 2026-04 | 2026-05 | 2026-06 | 2026-07 | 2026-08 | 2026-09 | 2026-10 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ADA | 21 | 19 | 34 | 28 | 20 | 21 | 17 | 27 | 32 | 27 | 19 | 25 | 33 | 25 | 39 | 30 | 24 | 18 | 17 | 20 | 30 | 5 |
| BNB | 20 | 20 | 18 | 20 | 14 | 16 | 22 | 27 | 16 | 27 | 32 | 30 | 25 | 28 | 27 | 25 | 20 | 19 | 28 | 20 | 19 | 2 |
| BTC | 33 | 22 | 27 | 33 | 31 | 36 | 33 | 24 | 35 | 23 | 30 | 32 | 29 | 30 | 26 | 30 | 26 | 29 | 34 | 26 | 26 | 2 |
| ETH | 24 | 23 | 21 | 27 | 24 | 32 | 17 | 22 | 25 | 25 | 22 | 27 | 22 | 25 | 39 | 24 | 38 | 20 | 27 | 28 | 29 | 0 |
| HYPE | 30 | 30 | 29 | 26 | 26 | 29 | 26 | 23 | 22 | 27 | 29 | 23 | 28 | 22 | 36 | 27 | 26 | 29 | 25 | 38 | 20 | 3 |
| LINK | 28 | 28 | 24 | 25 | 20 | 32 | 24 | 30 | 23 | 28 | 29 | 37 | 30 | 19 | 29 | 29 | 27 | 24 | 25 | 23 | 18 | 2 |
| SOL | 19 | 12 | 26 | 30 | 24 | 22 | 21 | 31 | 23 | 30 | 23 | 35 | 25 | 20 | 30 | 31 | 25 | 26 | 20 | 30 | 25 | 2 |
| XAUT | 0 | 0 | 0 | 17 | 16 | 23 | 16 | 21 | 22 | 16 | 19 | 29 | 23 | 21 | 21 | 28 | 24 | 22 | 21 | 34 | 23 | 5 |

## Tabla 3: secundario NC* por bloque (solo versiones completas; no entra al criterio de fase 1)

| simbolo | C1 | C2 |
|---|---|---|
| NCCO1OILBRENT2USD | 0 | 147 |
| NCCOXAG2USD | 3 | 167 |
| NCSINASDAQ1002USD | 71 | 170 |
| NCSISP5002USD | 63 | 167 |
| NCSKAAPL2USD | 55 | 163 |
| NCSKAMZN2USD | 58 | 128 |
| NCSKGOOGL2USD | 54 | 139 |
| NCSKMETA2USD | 41 | 153 |
| NCSKNVDA2USD | 46 | 142 |
