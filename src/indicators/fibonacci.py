"""
Fibonacci para V5: zona de entrada (61.8%-88.6% de retroceso del impulso,
mismo criterio que fibo-reversal-bot) + niveles de gestión de salida
(23.6/38.2/50/61.8/78.6% del leg A->B), tal como se explica en el video
"CURSO FIBONACCI #2" (BITLOBO TRADING).
"""
from dataclasses import dataclass


@dataclass
class EntryZone:
    direction: str        # 'up' (impulso alcista, entrada en largo en el retroceso)
                           # 'down' (impulso bajista, entrada en corto en el rebote)
    level_618: float
    level_786: float
    level_886: float
    zone_upper: float
    zone_lower: float


def compute_entry_zone(a_price: float, b_price: float, direction: str) -> EntryZone:
    """a_price/b_price: extremos del impulso (A=inicio, B=fin, antes del retroceso)."""
    move = abs(b_price - a_price)
    if direction == "up":
        level_618 = b_price - move * 0.618
        level_786 = b_price - move * 0.786
        level_886 = b_price - move * 0.886
        zone_upper, zone_lower = level_618, level_786
    elif direction == "down":
        level_618 = b_price + move * 0.618
        level_786 = b_price + move * 0.786
        level_886 = b_price + move * 0.886
        zone_upper, zone_lower = level_786, level_618
    else:
        raise ValueError("direction debe ser 'up' o 'down'")
    return EntryZone(direction=direction, level_618=level_618, level_786=level_786,
                      level_886=level_886, zone_upper=zone_upper, zone_lower=zone_lower)


def compute_exit_levels(swing_high: float, swing_low: float) -> dict:
    """
    Niveles de gestión de salida, medidos como retroceso del leg
    swing_high<->swing_low: level(pct) = low + pct*(high-low). El precio
    "recuperando" ese % del leg hacia el otro extremo es el objetivo.
    Devuelve los 5 niveles que usa el video: 23.6/38.2/50/61.8/78.6%.
    """
    move = swing_high - swing_low
    return {
        "level_236": swing_low + move * 0.236,
        "level_382": swing_low + move * 0.382,
        "level_500": swing_low + move * 0.500,
        "level_618": swing_low + move * 0.618,
        "level_786": swing_low + move * 0.786,
    }
