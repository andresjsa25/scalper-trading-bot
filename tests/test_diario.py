import unittest
import diario_trades as d

LOG = ["2026-08-04 14:16:54 [ORDEN REAL ENVIADA] BNB/USDT:USDT v1_sniper sell 0.1 size=2.0 entry~=100.0 SL=105.0 TP=90.0 -> orderId=111"]


def fila(oid, t, tipo, px, qty, fee, pnl, lev="15X", pair="BNB-USDT"):
    return {"Order No.": oid, "Time(Asia/Shanghai)": t, "Pair": pair, "Type": tipo,
            "Leverage": lev, "DealPrice": str(px), "Quantity": str(qty), "Fee": str(fee),
            "Realized PNL": str(pnl), "Order Type": "Autonomous Orders"}


class TestDiario(unittest.TestCase):
    def test_log(self):
        o = d.parsear_log(LOG)
        self.assertEqual(o["111"]["pair"], "BNB-USDT")
        self.assertEqual(o["111"]["strat"], "v1_sniper")

    def test_trade_con_match_y_R(self):
        # 22:16 Shanghai = 14:16 UTC (ventana NY: 13:30-16)
        f = d.leer_export([
            fila("111", "2026-08-04 22:16:56", "Open Short", 100, 2, -0.1, 0),
            fila("222", "2026-08-04 23:00:00", "Close Short", 95, 2, -0.1, 10),
        ])
        t = d.armar_trades(f, d.parsear_log(LOG))
        self.assertEqual(len(t), 1)
        self.assertEqual(t[0]["estrategia"], "v1_sniper")
        self.assertEqual(t[0]["ventana"], "NY")
        self.assertAlmostEqual(t[0]["neto"], 9.8)
        self.assertAlmostEqual(t[0]["R"], 0.98)  # riesgo = 2*5 = 10

    def test_sin_match_y_cierre_parcial(self):
        f = d.leer_export([
            fila("9", "2026-08-05 10:00:00", "Open Long", 10, 4, -0.01, 0, lev="50X"),
            fila("10", "2026-08-05 11:00:00", "Close Long", 11, 2, -0.01, 2, lev="50X"),
            fila("11", "2026-08-05 12:00:00", "Close Long", 12, 2, -0.01, 4, lev="50X"),
        ])
        t = d.armar_trades(f, {})
        self.assertEqual(len(t), 1)
        self.assertEqual(t[0]["estrategia"], "sin_match")
        self.assertEqual(t[0]["apalancamiento"], "50X")
        self.assertEqual(t[0]["R"], "")
        self.assertAlmostEqual(t[0]["neto"], 5.97)

    def test_posicion_abierta_y_resumen(self):
        f = d.leer_export([fila("9", "2026-08-05 10:00:00", "Open Long", 10, 4, -0.01, 0)])
        t = d.armar_trades(f, {})
        self.assertEqual(t[0]["estado"], "abierta")
        self.assertIn("abiertos: 1", d.texto_resumen(t))

    def test_ventanas(self):
        from datetime import datetime, timezone
        u = lambda h, m: datetime(2026, 1, 1, h, m, tzinfo=timezone.utc)
        self.assertEqual(d.ventana(u(13, 29)), "londres")
        self.assertEqual(d.ventana(u(13, 30)), "NY")
        self.assertEqual(d.ventana(u(16, 0)), "otra")
        self.assertEqual(d.ventana(u(22, 0)), "noche")


if __name__ == "__main__":
    unittest.main()
