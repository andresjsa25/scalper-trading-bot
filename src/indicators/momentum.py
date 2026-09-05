"""
RSI y MACD -- indicadores de momentum pedidos por el usuario (2026-08-25)
para una estrategia exploratoria de confluencia (ver strategy_v7_confluence.py).
Ninguno de los dos existía en el proyecto todavía (V1/sanchezzfx usan EMA +
estructura + ATR + volumen relativo, no osciladores de momentum).

RSI: fórmula estándar de Wilder (suavizado exponencial tipo Wilder, no SMA
simple -- es la definición original y la que usan la mayoría de plataformas,
incluida la que aparece en la captura de pantalla del usuario).

MACD: EMA rápida - EMA lenta (línea MACD), EMA de esa línea (línea de señal),
histograma = línea MACD - señal. Períodos estándar 12/26/9, iguales a los
que trae por defecto BingX (según la captura del usuario: "MACD(12,26,9)").

Cruce + retest (find_macd_retest_triggers): el usuario describió el patrón
así (2026-08-25): "cuando la línea roja [MACD] cruza la azul [señal], indica
la dirección del mercado, muchas veces en el retest es cuando está la mejor
oportunidad para entrar, pero muchas veces es erróneo" -- de ahí que en la
estrategia el retest sea UNA confluencia más, no la señal por sí sola.

Definición medible del retest (mi traducción, ajustable si el backtest no
calza): tras un cruce alcista (línea MACD pasa de por debajo a por encima de
la señal), el histograma (línea - señal) empieza a crecer desde 0. Se guarda
el máximo del histograma alcanzado desde el cruce. El retest dispara en la
primera vela en que el histograma cae a RETEST_RETRACE_FRAC (30% por
defecto) o menos de ese máximo, siempre que siga siendo positivo (si cruza
de nuevo a negativo, el cruce se invalida, no hay retest). Se usa una
FRACCIÓN del máximo del histograma en vez de un umbral absoluto porque el
MACD está en la escala de precio del activo (no es lo mismo un histograma
de 50 en BTC a ~80.000 que uno de 0.001 en ADA a ~0.5) -- así la misma
regla sirve para los 10 símbolos de config.py sin normalizar a mano.

Sin look-ahead: el escaneo es un solo pase hacia adelante, cada vela solo
usa datos de velas anteriores o la propia (igual que market_structure_at_each_bar
en trend.py).
"""
import pandas as pd


def add_rsi(df: pd.DataFrame, period: int = 14, col_name: str = "rsi") -> pd.DataFrame:
    df = df.copy()
    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    # Suavizado de Wilder = EMA con alpha = 1/period (equivalente a com=period-1)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss
    df[col_name] = 100 - (100 / (1 + rs))
    df.loc[avg_loss == 0, col_name] = 100.0  # sin pérdidas en la ventana -> RSI 100 (evita división por cero)
    return df


def add_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9,
             prefix: str = "macd") -> pd.DataFrame:
    df = df.copy()
    ema_fast = df["close"].ewm(span=fast, adjust=False).mean()
    ema_slow = df["close"].ewm(span=slow, adjust=False).mean()

    macd_line = ema_fast - ema_slow
    macd_signal = macd_line.ewm(span=signal, adjust=False).mean()

    df[f"{prefix}_line"] = macd_line
    df[f"{prefix}_signal"] = macd_signal
    df[f"{prefix}_hist"] = macd_line - macd_signal
    return df


def detect_macd_cross(df: pd.DataFrame, prefix: str = "macd") -> pd.DataFrame:
    """Marca la vela EXACTA donde ocurre el cruce (no el estado, el evento)."""
    df = df.copy()
    hist = df[f"{prefix}_hist"]
    hist_prev = hist.shift(1)

    df[f"{prefix}_cross_bull"] = (hist_prev <= 0) & (hist > 0)
    df[f"{prefix}_cross_bear"] = (hist_prev >= 0) & (hist < 0)
    return df


def detect_rsi_extreme_exit(df: pd.DataFrame, rsi_col: str = "rsi",
                             overbought: float = 70, oversold: float = 30) -> pd.DataFrame:
    """
    Agregado 2026-08-25 a pedido del usuario para strategy_v8_rsi_confluence.py:
    "cuando el RSI está en sobrecompra o sobreventa, buscar qué está
    pasando con los otros indicadores en ese momento para predecir el
    siguiente movimiento". La señal NO es "RSI entra en la zona extrema"
    (eso dispararía en pleno movimiento, antes de cualquier confirmación
    de agotamiento) sino "RSI SALE de la zona extrema" -- el cruce de
    vuelta hacia el centro es la confirmación mínima de que el extremo ya
    pasó, más fácil de explicar y de ver en vivo que perseguir el pico exacto.

    Vectorizado (sin loop): compara cada vela contra la anterior.
    """
    df = df.copy()
    rsi = df[rsi_col]
    rsi_prev = rsi.shift(1)

    df["rsi_exit_overbought"] = (rsi_prev >= overbought) & (rsi < overbought)
    df["rsi_exit_oversold"] = (rsi_prev <= oversold) & (rsi > oversold)
    return df


def add_macd_turning(df: pd.DataFrame, prefix: str = "macd") -> pd.DataFrame:
    """
    Confluencia de momentum para v8: '¿el histograma ya empezó a girar
    a favor de la nueva dirección?' -- más simple y más rápido de leer a
    mano que esperar un cruce completo de MACD (eso puede tardar mucho
    más que el propio movimiento de RSI que se está tradeando).
    """
    df = df.copy()
    hist_diff = df[f"{prefix}_hist"].diff()
    df[f"{prefix}_turning_up"] = hist_diff > 0
    df[f"{prefix}_turning_down"] = hist_diff < 0
    return df


def find_macd_retest_triggers(df: pd.DataFrame, prefix: str = "macd",
                               retrace_frac: float = 0.3,
                               max_bars_after_cross: int = 20) -> pd.DataFrame:
    """
    Recorrido O(n) con estado (una sola pasada hacia adelante). Para cada
    cruce alcista/bajista detectado por detect_macd_cross, sigue el
    histograma vela a vela hasta max_bars_after_cross buscando el primer
    retest (ver docstring del módulo). Si el histograma vuelve a cruzar
    cero antes del retest, el cruce se invalida (se descarta, no cuenta
    como señal fallida ni exitosa -- simplemente no hay setup).

    Devuelve el df con dos columnas nuevas: '{prefix}_retest_long' y
    '{prefix}_retest_short' (bool), True en la vela donde se confirma el
    retest de un cruce alcista/bajista respectivamente.
    """
    df = df.copy()
    hist = df[f"{prefix}_hist"].values
    cross_bull = df[f"{prefix}_cross_bull"].values
    cross_bear = df[f"{prefix}_cross_bear"].values

    n = len(df)
    retest_long = [False] * n
    retest_short = [False] * n

    # estado del cruce alcista activo: (pos_cruce, max_hist_desde_cruce) o None
    active_bull = None
    active_bear = None

    for i in range(n):
        if cross_bull[i]:
            active_bull = [i, hist[i]]
        if cross_bear[i]:
            active_bear = [i, hist[i]]

        if active_bull is not None:
            start_pos, max_hist = active_bull
            if hist[i] <= 0:
                active_bull = None  # se invalidó (volvió a cruzar antes del retest)
            elif i - start_pos > max_bars_after_cross:
                active_bull = None  # se venció la ventana sin retest
            else:
                if hist[i] > max_hist:
                    active_bull[1] = hist[i]
                    max_hist = hist[i]
                elif i > start_pos and hist[i] <= max_hist * retrace_frac:
                    retest_long[i] = True
                    active_bull = None  # ya disparó, no re-disparar en el mismo cruce

        if active_bear is not None:
            start_pos, min_hist = active_bear  # 'max_hist' acá es el más negativo (magnitud máxima)
            if hist[i] >= 0:
                active_bear = None
            elif i - start_pos > max_bars_after_cross:
                active_bear = None
            else:
                if hist[i] < min_hist:
                    active_bear[1] = hist[i]
                    min_hist = hist[i]
                elif i > start_pos and hist[i] >= min_hist * retrace_frac:
                    retest_short[i] = True
                    active_bear = None

    df[f"{prefix}_retest_long"] = retest_long
    df[f"{prefix}_retest_short"] = retest_short
    return df
