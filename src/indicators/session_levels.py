"""
Niveles de liquidez de sesión/día + clasificación Run vs Sweep, tal como
se describen (verbalmente, sin cifras exactas) en el video SANCHEZZFX
"El Trading es dificil hasta que aplicas estos 2 conceptos"
(https://youtu.be/lAN39MqDIQQ). Traducción a reglas medibles -- documentada
para que se pueda corregir si no calza con el video:

  - "Elige un nivel: máximo/mínimo de la sesión de Asia, de Londres o del
    día anterior" -> el video no da horas UTC exactas para Asia/Londres.
    Se usan las mismas fronteras que config.SESSION_WINDOWS_UTC ya usa
    para Londres/NY (Londres abre 8:00 UTC, NY abre 13:30 UTC), y Asia
    como el tramo previo a Londres:
        ASIA    00:00 - 08:00 UTC
        LONDON  08:00 - 13:30 UTC
        NEWYORK 13:30 - 21:00 UTC   (cierre aprox. NY, 16:00 EST)
        PREVDAY día calendario UTC completo anterior (00:00 - 24:00 UTC)
    El nivel de una sesión queda "activo" (disponible para ser barrido)
    desde el cierre de esa ventana hasta el cierre de la MISMA ventana al
    día siguiente (se reemplaza por el nuevo). PREVDAY queda activo
    durante todo el día calendario siguiente.

  - "La vela llega al nivel, lo rompe y CIERRA con el cuerpo por encima/
    debajo de la vela anterior" = Liquidity RUN -> continuación, no se
    opera. "La vela SOBREPASA el nivel con una mecha pero CIERRA de
    vuelta" = Liquidity SWEEP/Swift -> señal. Clasificado acá contra el
    NIVEL DE SESIÓN (no contra la vela anterior genérica, a diferencia de
    detect_liquidity_swift() en patterns.py que sí es vela-a-vela --
    functions separadas a propósito, este es el barrido del nivel
    específico que pide el video).
"""
import pandas as pd

SESSION_WINDOWS_UTC = {
    "asia": ("00:00", "08:00"),
    "london": ("08:00", "13:30"),
    "newyork": ("13:30", "21:00"),
}


def _time_in_window(ts: pd.Timestamp, start: str, end: str) -> bool:
    t = ts.time()
    start_t = pd.Timestamp(start).time()
    end_t = pd.Timestamp(end).time()
    return start_t <= t < end_t


def compute_session_levels(df: pd.DataFrame, level_type: str) -> pd.DataFrame:
    """
    Agrega columnas `level_high` / `level_low` al df (misma temporalidad
    que se le pase, pensado para 1h) con el nivel de sesión/día VIGENTE en
    cada vela -- ya desplazado en el tiempo para no usar datos del futuro
    (el nivel de hoy se calcula con las velas de hoy, pero solo queda
    "activo" para el resto de las velas, no para las velas de la propia
    sesión que lo generó).

    level_type: 'asia' | 'london' | 'newyork' | 'prevday'
    """
    df = df.copy().reset_index(drop=True)
    dt = df["datetime"]
    utc_date = dt.dt.date

    if level_type == "prevday":
        daily_high = df.groupby(utc_date)["high"].max()
        daily_low = df.groupby(utc_date)["low"].min()
        prev_high = daily_high.shift(1)
        prev_low = daily_low.shift(1)
        df["level_high"] = utc_date.map(prev_high)
        df["level_low"] = utc_date.map(prev_low)
        return df

    start, end = SESSION_WINDOWS_UTC[level_type]
    in_window = dt.apply(lambda ts: _time_in_window(ts, start, end))

    session_high = df.loc[in_window].groupby(utc_date[in_window])["high"].max()
    session_low = df.loc[in_window].groupby(utc_date[in_window])["low"].min()

    # El nivel del día D queda vigente desde el cierre de su ventana (día D)
    # hasta el cierre de la misma ventana al día siguiente (día D+1) -- se
    # asigna a cada vela el nivel de "ayer" si la vela cae DENTRO o ANTES
    # de cerrarse hoy la ventana, y el de "hoy" una vez la ventana de hoy
    # ya cerró.
    level_high_col = [None] * len(df)
    level_low_col = [None] * len(df)
    end_t = pd.Timestamp(end).time()

    sorted_days = sorted(session_high.index)
    for i in range(len(df)):
        ts = dt.iloc[i]
        d = utc_date.iloc[i]
        # ¿la ventana del día D ya cerró a esta hora?
        window_closed_today = ts.time() >= end_t
        ref_day = d if window_closed_today else _prev_available_day(d, sorted_days)
        if ref_day is None or ref_day not in session_high.index:
            continue
        level_high_col[i] = session_high[ref_day]
        level_low_col[i] = session_low[ref_day]

    df["level_high"] = level_high_col
    df["level_low"] = level_low_col
    return df


def _prev_available_day(d, sorted_days):
    prev = None
    for day in sorted_days:
        if day >= d:
            break
        prev = day
    return prev


def detect_level_sweep(df: pd.DataFrame) -> pd.DataFrame:
    """
    Requiere que compute_session_levels() ya haya corrido (columnas
    level_high/level_low presentes). Clasifica cada vela contra SU nivel
    vigente:
      - sweep_high: mecha por encima de level_high, cierre de vuelta por
        debajo -> Liquidity Sweep de un máximo (sesgo VENTA).
      - sweep_low: mecha por debajo de level_low, cierre de vuelta por
        encima -> Liquidity Sweep de un mínimo (sesgo COMPRA).
      - run_high / run_low: igual pero el CIERRE queda del otro lado
        (continuación, "no es nuestro sitio todavía" según el video) --
        se marcan para poder excluir explícitamente esas velas de la
        búsqueda de entrada, no solo para no contarlas como sweep.
    """
    df = df.copy()
    n = len(df)
    sweep_high = [False] * n
    sweep_low = [False] * n
    run_high = [False] * n
    run_low = [False] * n

    high = df["high"].values
    low = df["low"].values
    close = df["close"].values
    lvl_high = df["level_high"].values
    lvl_low = df["level_low"].values

    for i in range(n):
        lh, ll = lvl_high[i], lvl_low[i]
        if lh is not None and high[i] > lh:
            if close[i] < lh:
                sweep_high[i] = True
            else:
                run_high[i] = True
        if ll is not None and low[i] < ll:
            if close[i] > ll:
                sweep_low[i] = True
            else:
                run_low[i] = True

    df["sweep_high"] = sweep_high
    df["sweep_low"] = sweep_low
    df["run_high"] = run_high
    df["run_low"] = run_low
    return df
