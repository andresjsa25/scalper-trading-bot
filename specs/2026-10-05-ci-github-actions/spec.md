# Spec: CI del bot en GitHub Actions

Repo público. Una rama, un PR, Andrés mergea. No tocar el bot en vivo ni la lógica de trading.

## Criterios de aceptación

1. `.github/workflows/ci.yml` corre en `pull_request` y en `push` a `main`. Instala dependencias y ejecuta `python -m pytest -q` con la versión de Python del bot (3.12, según `run_live_trading.bat`). Permisos mínimos (`contents: read`), sin secrets, sin `pull_request_target`. Las actions van pineadas a versión.
2. El mismo workflow incluye un escaneo de secretos con gitleaks que falla el PR si encuentra uno. No se prueba subiendo secretos, ni falsos, al repo público.
3. `.gitignore` cubre `.env*`, `data/`, `logs/` y los exports de BingX. Si falta algo, se agrega.
4. `CLAUDE.md` del bot tiene una línea con `python -m pytest -q` como comando de verificación.
5. Una rama, un PR, revisión con `/revisar` (una vuelta).

## Fuera de alcance

- Cambios en la lógica de trading, en `run_live_trading.py` o en el bot en vivo.
