"""Tests del parche de ventanas horarias, V5 apagado y riesgo 1% (sin red)."""
import os, sys, types, unittest
from unittest import mock

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "src"))

import live_trading as lt  # noqa: E402
import run_live_trading as rl  # noqa: E402


def ts(hhmm, day="2026-10-05"):
    return pd.Timestamp(f"{day} {hhmm}:00", tz="UTC")


class InWindows(unittest.TestCase):
    def test_limites_semiabiertos(self):
        w = [rl.NY_OPEN_WINDOW]
        self.assertFalse(rl.in_windows(ts("13:29"), w))
        self.assertTrue(rl.in_windows(ts("13:30"), w))
        self.assertTrue(rl.in_windows(ts("15:59"), w))
        self.assertFalse(rl.in_windows(ts("16:00"), w))

    def test_noche_hasta_medianoche(self):
        w = [rl.NIGHT_WINDOW]
        self.assertFalse(rl.in_windows(ts("20:59"), w))
        self.assertTrue(rl.in_windows(ts("21:00"), w))
        self.assertTrue(rl.in_windows(ts("23:59"), w))
        self.assertFalse(rl.in_windows(ts("00:00", "2026-10-06"), w))

    def test_sin_ventanas_no_filtra_y_acepta_naive(self):
        self.assertTrue(rl.in_windows(ts("03:00"), None))
        self.assertTrue(rl.in_windows(pd.Timestamp("2026-10-05 14:00:00"), [rl.NY_OPEN_WINDOW]))

    def test_convierte_a_utc(self):
        t = pd.Timestamp("2026-10-05 11:00:00", tz="America/Argentina/Buenos_Aires")  # 14:00 UTC
        self.assertTrue(rl.in_windows(t, [rl.NY_OPEN_WINDOW]))


class VentanasPorEstrategia(unittest.TestCase):
    def test_v1_acciones_solo_ny(self):
        for sym in ("NCSKAAPL2USD/USDT:USDT", "NCSKGOOGL2USD/USDT:USDT", "NCSISP5002USD/USDT:USDT"):
            w = rl.V1_WINDOWS_BY_SYMBOL[sym]
            self.assertTrue(rl.in_windows(ts("14:00"), w))
            self.assertFalse(rl.in_windows(ts("22:00"), w), sym)

    def test_v1_cripto_y_commodities_ny_y_noche(self):
        for sym in ("BTC/USDT:USDT", "SOL/USDT:USDT", "XAUT/USDT:USDT", "NCCO1OILBRENT2USD/USDT:USDT", "NCCOXAG2USD/USDT:USDT"):
            w = rl.V1_WINDOWS_BY_SYMBOL[sym]
            self.assertTrue(rl.in_windows(ts("14:00"), w), sym)
            self.assertTrue(rl.in_windows(ts("22:00"), w), sym)

    def test_v1_sin_londres_ni_asia(self):
        for sym, w in rl.V1_WINDOWS_BY_SYMBOL.items():
            for hhmm in ("03:00", "08:30", "09:30", "12:00", "18:00"):
                self.assertFalse(rl.in_windows(ts(hhmm), w), f"{sym} {hhmm}")

    def test_todos_los_simbolos_de_v1_tienen_ventanas(self):
        self.assertEqual(set(rl.V1_WINDOWS_BY_SYMBOL), set(rl.V1_LIVE_CONFIG))

    def test_v10_solo_londres_por_hora_de_entrada(self):
        f = lambda hhmm: rl.in_windows(ts(hhmm), rl.V10_WINDOWS, rl.V10_ENTRY_OFFSET_MIN)
        self.assertFalse(f("06:00"))  # entra 07:00
        self.assertTrue(f("07:00"))   # entra 08:00
        self.assertTrue(f("12:00"))   # entra 13:00
        self.assertFalse(f("13:00"))  # entra 14:00
        self.assertFalse(f("22:00"))

    def test_v5_apagado_y_v1_config_intacta(self):
        self.assertEqual(rl.V5_LIVE_CONFIG, {})
        # V1_LIVE_CONFIG no se altera: los scripts de análisis la importan
        for cfg in rl.V1_LIVE_CONFIG.values():
            self.assertNotIn("windows", cfg)


class RiesgoVivo(unittest.TestCase):
    def test_usa_live_risk_pct_y_no_el_del_setup(self):
        setup = types.SimpleNamespace(symbol="BTC/USDT:USDT", strategy="v1_sniper", risk_pct=0.02,
                                      entry_price_target=100.0, stop_price=99.0,
                                      signal_datetime="2026-10-05T14:00:00+00:00")
        with mock.patch.object(lt, "kill_switch_active", return_value=False), \
             mock.patch.object(lt, "log"), \
             mock.patch.object(lt, "set_leverage_strict", return_value=True), \
             mock.patch.object(lt, "compute_valid_position_size", return_value=(1.0, 1.0)) as sized, \
             mock.patch.object(lt, "place_entry_with_sl_tp", return_value={"id": "1"}):
            rl.process_new_setups(object(), [setup], {"open_orders": []}, 200.0, 100.0, 0.0, 0, 15, set())
        self.assertEqual(rl.LIVE_RISK_PCT, 0.02)
        self.assertEqual(sized.call_args[0][3], 0.02)


if __name__ == "__main__":
    unittest.main()
