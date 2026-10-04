"""Criterio 4 (deduplicacion de 8 velas y referencia al azar) y criterio 5 (bootstrap por dia reproducible)."""
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from estudio_sinteticos import velas  # noqa: E402
from estudio_eventos.muestreo import deduplicar, referencia_azar, bootstrap_dia  # noqa: E402


def _eventos(posiciones, simbolo="BTC", tf="1h", sentido="long"):
    return pd.DataFrame({"simbolo": simbolo, "tf": tf, "sentido": sentido, "pos": posiciones})


class TestDeduplicacion:
    def test_no_cuenta_otro_evento_dentro_de_las_8_velas_siguientes(self):
        # 10 cuenta. 12 (+2) y 18 (+8) quedan bloqueados. 19 (+9) cuenta. 27 (+8 desde 19) queda bloqueado.
        res = deduplicar(_eventos([10, 12, 18, 19, 27]), ventana=8)
        assert res["pos"].tolist() == [10, 19]

    def test_evento_a_9_velas_del_anterior_si_cuenta(self):
        res = deduplicar(_eventos([50, 59]), ventana=8)
        assert res["pos"].tolist() == [50, 59]

    def test_el_bloqueo_es_por_simbolo_sentido_y_temporalidad(self):
        eventos = pd.concat([
            _eventos([10], "BTC", "1h", "long"),
            _eventos([11], "BTC", "1h", "short"),   # otro sentido: cuenta
            _eventos([12], "BTC", "4h", "long"),    # otra temporalidad: cuenta
            _eventos([13], "ETH", "1h", "long"),    # otro simbolo: cuenta
        ], ignore_index=True)
        res = deduplicar(eventos, ventana=8)
        assert sorted(res["pos"].tolist()) == [10, 11, 12, 13]


class TestReferenciaAlAzar:
    def setup_method(self):
        # 2800 velas horarias: primeras 2400 en bloque E (100 por hora del dia), resto en C1.
        self.df = velas([(100, 101, 99, 100)] * 2800, inicio="2025-01-01 00:00")
        self.df["bloque"] = ["E"] * 2400 + ["C1"] * 400
        self.evento = 1212  # hora 12 UTC, bloque E
        rng = np.random.default_rng(5)
        self.excluir = rng.random(2800) < 0.3
        self.excluir[self.evento] = True

    def test_veinte_velas_con_misma_hora_y_bloque_sin_eventos(self):
        res = referencia_azar(self.df, self.evento, self.excluir, n=20, semilla=7)
        assert len(res) == 20
        assert len(set(res)) == 20
        assert all(self.df.index[p].hour == 12 for p in res)
        assert all(self.df["bloque"].iloc[p] == "E" for p in res)
        assert not any(self.excluir[p] for p in res)
        assert self.evento not in res

    def test_solo_elige_entre_velas_no_excluidas(self):
        # Solo quedan 20 candidatas validas (hora 12, bloque E, sin evento): la referencia debe ser exactamente ese conjunto.
        candidatas = [p for p in range(2400) if p % 24 == 12 and p != self.evento][:20]
        excluir = np.ones(2800, dtype=bool)
        excluir[candidatas] = False
        res = referencia_azar(self.df, self.evento, excluir, n=20, semilla=7)
        assert sorted(res) == sorted(candidatas)

    def test_misma_semilla_mismo_resultado(self):
        a = referencia_azar(self.df, self.evento, self.excluir, n=20, semilla=7)
        b = referencia_azar(self.df, self.evento, self.excluir, n=20, semilla=7)
        assert a == b


def _eventos_dia(seed=0, n=200, dias=60):
    rng = np.random.default_rng(seed)
    return pd.DataFrame({"dia": rng.integers(0, dias, n), "retorno": rng.normal(0.1, 1.0, n)})


class TestBootstrapPorDia:
    def test_misma_semilla_dos_corridas_identicas(self):
        df = _eventos_dia()
        a = bootstrap_dia(df, "retorno", n_boot=500, semilla=42)
        b = bootstrap_dia(df, "retorno", n_boot=500, semilla=42)
        assert a == b

    def test_no_depende_del_estado_global_del_generador(self):
        df = _eventos_dia()
        np.random.seed(1)
        a = bootstrap_dia(df, "retorno", n_boot=500, semilla=42)
        np.random.seed(2)
        np.random.rand(100)
        b = bootstrap_dia(df, "retorno", n_boot=500, semilla=42)
        assert a == b

    def test_intervalo_contiene_la_media(self):
        media, lo, hi = bootstrap_dia(_eventos_dia(), "retorno", n_boot=500, semilla=42)
        assert lo <= media <= hi
