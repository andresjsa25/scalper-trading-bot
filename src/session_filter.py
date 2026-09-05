"""Filtro de horario de sesión (Londres/Nueva York), en UTC, según config.SESSION_WINDOWS_UTC."""
import pandas as pd

import config


def in_session(dt: pd.Timestamp) -> bool:
    t = dt.tz_convert("UTC").strftime("%H:%M")
    for start, end in config.SESSION_WINDOWS_UTC:
        if start <= t <= end:
            return True
    return False
