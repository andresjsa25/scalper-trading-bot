# Estado: CI del bot en GitHub Actions

Fase actual: PR #15 abierto, en revisión (vuelta 1).

## Registro

- 2026-10-05 · sesión principal (Claude) · Rama `ci/github-actions` desde `origin/main` (2ab2cac). Commits: `.gitignore`, workflow `ci.yml`, `CLAUDE.md`. Tests en export limpio: 122 passed, 1 skipped. Gitleaks sobre el historial: 0 hallazgos; compuerta probada con clave falsa en repo descartable (exit 1). PR #15 abierto contra `main`. Pendiente: Actions real en Ubuntu (no probado localmente).
- 2026-10-05 · revisor (vuelta 1, PR #15) · Veredicto: Aprobar. Altos: ninguno. Medio 1 (corregido por la sesión principal): `.gitignore` no cubría `BingX_OrderHistory.csv`, `Order History.csv` ni `orders_history.csv`; patrón cambiado a `*[Oo]rder*[Hh]istory*`, verificado con `git check-ignore --no-index` sobre esos nombres y sobre `README.md` (no ignorado). Medio 2 (pendiente, no bloquea): `requirements.txt` sin versiones y `pytest` sin fijar; `ubuntu-latest` puede cambiar. Opciones: archivo de constraints generado con `pip freeze`, o `ubuntu-24.04` como mínimo. Bajo 3 (pendiente, no bloquea): sin `.gitleaks.toml`; agregarlo solo si aparece un falso positivo, en PR aparte. Bajo 4 (aclarado): la compuerta con clave falsa sí se corrió en esta sesión en un repo descartable y dio exit 1; el run real en Actions sigue pendiente.
