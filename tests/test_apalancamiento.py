"""Tests del fix de apalancamiento (sin red ni claves: exchange falso)."""
import os, sys, types, unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "src"))

import live_trading as lt  # noqa: E402
import run_live_trading as rl  # noqa: E402


class FakeExchange:
    def __init__(self, fail_on=None):
        self.calls = []
        self.fail_on = fail_on or (lambda lev, sym, side: False)

    def set_leverage(self, lev, symbol, params=None):
        side = (params or {}).get("side")
        self.calls.append((symbol, lev, side))
        if self.fail_on(lev, symbol, side):
            raise Exception('bingx {"code":101253,"msg":"Insufficient margin"}')


def setup_fake(symbol="NCSKGOOGL2USD/USDT:USDT", strategy="v1_sniper"):
    return types.SimpleNamespace(
        symbol=symbol, strategy=strategy, risk_pct=0.02, entry_price_target=100.0,
        stop_price=99.0, signal_datetime="2026-10-02T14:00:00+00:00")


class SetLeverageStrict(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(lt, "log")
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_ok_en_ambos_lados(self):
        ex = FakeExchange()
        self.assertTrue(lt.set_leverage_strict(ex, "BTC/USDT:USDT", 15, sleep=lambda s: None))
        self.assertEqual(ex.calls, [("BTC/USDT:USDT", 15, "LONG"), ("BTC/USDT:USDT", 15, "SHORT")])

    def test_falla_si_un_lado_no_se_puede_fijar(self):
        ex = FakeExchange(fail_on=lambda lev, sym, side: side == "SHORT")
        self.assertFalse(lt.set_leverage_strict(ex, "BTC/USDT:USDT", 15, retries=2, sleep=lambda s: None))

    def test_reintenta_y_se_recupera(self):
        estado = {"n": 0}

        def falla_una_vez(lev, sym, side):
            estado["n"] += 1
            return estado["n"] == 1

        ex = FakeExchange(fail_on=falla_una_vez)
        self.assertTrue(lt.set_leverage_strict(ex, "BTC/USDT:USDT", 15, retries=3, sleep=lambda s: None))


class ProcessNewSetupsTests(unittest.TestCase):
    def correr(self, ex, setup, leverage):
        state = {"open_orders": []}
        real = lt.set_leverage_strict
        with mock.patch.object(lt, "kill_switch_active", return_value=False), \
             mock.patch.object(lt, "log"), \
             mock.patch.object(lt, "compute_valid_position_size", return_value=(1.0, 2.0)) as sized, \
             mock.patch.object(lt, "place_entry_with_sl_tp", return_value={"id": "123"}) as place, \
             mock.patch.object(lt, "set_leverage_strict",
                               side_effect=lambda e, s, l: real(e, s, l, retries=1, sleep=lambda x: None)):
            rl.process_new_setups(ex, [setup], state, 200.0, 100.0, 0.0, 0, leverage, set())
        return state, sized, place

    def test_v1_en_googl_usa_15x_aunque_v5_use_50x(self):
        ex = FakeExchange()
        state, sized, place = self.correr(ex, setup_fake(strategy="v1_sniper"), rl.V1_LEVERAGE)
        self.assertTrue(ex.calls and all(lev == 15 for _, lev, _ in ex.calls))
        self.assertEqual(sized.call_args[0][6], 15)
        place.assert_called_once()
        self.assertEqual(len(state["open_orders"]), 1)

    def test_v5_en_googl_usa_50x(self):
        ex = FakeExchange()
        self.correr(ex, setup_fake(strategy="v5_fib_pullback"), rl.V5_LEVERAGE)
        self.assertTrue(ex.calls and all(lev == 50 for _, lev, _ in ex.calls))

    def test_si_falla_el_apalancamiento_no_abre_orden(self):
        ex = FakeExchange(fail_on=lambda lev, sym, side: True)
        state, sized, place = self.correr(ex, setup_fake(), rl.V1_LEVERAGE)
        place.assert_not_called()
        sized.assert_not_called()
        self.assertEqual(state["open_orders"], [])

    def test_no_hay_mapa_por_simbolo_que_pise_apalancamientos(self):
        self.assertFalse(hasattr(rl, "LEVERAGE_BY_SYMBOL"))


if __name__ == "__main__":
    unittest.main()
