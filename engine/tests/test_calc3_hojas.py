"""Matemática III: ejercicios de las hojas 15-20 resueltos por la operación calc3.
Referencia: respuestas impresas en las hojas (salvo las discrepancias documentadas en LIMITACIONES)."""
import math
import re
import pytest
from math_universe_engine.dispatcher import handle


def call(p):
    r = handle({"operation": "calc3", "params": p})
    return r


def aprox(r):
    return float(re.search(r"-?\d+\.?\d*(?:e-?\d+)?", str(r["approximate_result"]).split("≈")[1]).group())


CASOS = [
    # (params, valor esperado aproximado)
    ({"tipo": "coordenadas", "que": "masa3d", "sistema": "cilindricas", "delta": "1+z",
      "niveles": [["z", "0", "4-r^2"], ["r", "0", "2"], ["theta", "0", "2*pi"]]}, 56 * math.pi / 3),
    ({"tipo": "triple_region", "que": "masa3d", "delta": "1", "z_inf": "0", "z_sup": "x",
      "curvas": ["x=y^2", "x=1"], "orden": "dydx"}, 0.8),
]


@pytest.mark.parametrize("p,esperado", CASOS)
def test_masa_solidos(p, esperado):
    r = call(p)
    assert r["status"] == "success_exact"
    assert r["verification"]["status"] == "passed"
    assert aprox(r) == pytest.approx(esperado, rel=1e-6)


def test_lagrange_xy_1():
    r = call({"tipo": "lagrange", "f": "x^2+y^2", "restricciones": ["x*y=1"], "variables": ["x", "y"]})
    assert r["status"].startswith("success")
    assert "(-1, -1)" in str(r) or "-1" in str(r)
