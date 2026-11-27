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


# ---- Hoja #19 completa (respuestas impresas como referencia) ----
T = lambda **k: k
H19 = [
    (T(tipo="iterada", f="y", niveles=[["z", "x-y", "x+y"], ["y", "0", "x"], ["x", "0", "3"]]), 27 / 2),
    (T(tipo="triple_region", f="6*x*y", z_inf="0", z_sup="1+x+y", curvas=["y=sqrt(x)", "y=0", "x=1"], orden="dydx"), 65 / 28),
    (T(tipo="triple_region", f="x^2+y^2", z_inf="0", z_sup="4-y", curvas=["y=x^2", "y=4"], orden="dxdy"), 23552 / 315),
    (T(tipo="triple_region", f="1", z_inf="0", z_sup="4-y", curvas=["y=x^2", "y=4"], orden="dxdy"), 256 / 15),
    (T(tipo="triple_region", f="1", z_inf="0", z_sup="1-y", curvas=["y=x^2", "y=1"], orden="dxdy"), 8 / 15),
    (T(tipo="coordenadas", sistema="cilindricas", f="sqrt(x^2+y^2)", niveles=[["z", "-5", "4"], ["r", "0", "4"], ["theta", "0", "2*pi"]]), 384 * math.pi),
    (T(tipo="coordenadas", sistema="cilindricas", f="x^2", niveles=[["z", "0", "2*r"], ["r", "0", "1"], ["theta", "0", "2*pi"]]), 2 * math.pi / 5),
    (T(tipo="coordenadas", sistema="cilindricas", f="1", niveles=[["z", "0", "2-r*cos(theta)"], ["r", "0", "1"], ["theta", "0", "2*pi"]]), 2 * math.pi),
    (T(tipo="coordenadas", sistema="cilindricas", f="1", niveles=[["z", "0", "r^2"], ["r", "0", "2*sin(theta)"], ["theta", "0", "pi"]]), 3 * math.pi / 2),
    (T(tipo="coordenadas", sistema="esfericas", f="x^2+y^2", niveles=[["rho", "2", "3"], ["phi", "0", "pi"], ["theta", "0", "2*pi"]]), 1688 * math.pi / 15),
    (T(tipo="coordenadas", sistema="esfericas", f="1", niveles=[["rho", "2", "4"], ["phi", "0", "pi/3"], ["theta", "0", "2*pi"]]), 56 * math.pi / 3),
    (T(tipo="coordenadas", sistema="esfericas", f="1", niveles=[["rho", "0", "2*cos(phi)"], ["phi", "0", "pi/4"], ["theta", "0", "2*pi"]]), math.pi),
    (T(tipo="cambio_variables_3d", f="z*(x^2+y^2)", viejas=["x", "y", "z"], nuevas=["r", "t", "z"],
       mapa={"x": "3*r*cos(t)", "y": "2*r*sin(t)", "z": "z"}, modo="directo",
       niveles=[["z", "0", "36*(1-r^2)"], ["r", "0", "1"], ["t", "0", "2*pi"]]), 2106 * math.pi),
]


@pytest.mark.parametrize("p,esperado", H19)
def test_hoja19(p, esperado):
    r = call(p)
    assert r["status"] == "success_exact", r
    assert r["verification"]["status"] == "passed"
    assert float(re.search(r"-?\d+\.?\d*", str(r["approximate_result"])).group()) == pytest.approx(esperado, rel=1e-6)


def test_hoja19_ej4_seis_ordenes():
    ordenes = [[["z", "0", "y"], ["x", "y", "1"], ["y", "0", "1"]], [["z", "0", "y"], ["y", "0", "x"], ["x", "0", "1"]],
               [["x", "y", "1"], ["z", "0", "y"], ["y", "0", "1"]], [["x", "y", "1"], ["y", "z", "1"], ["z", "0", "1"]],
               [["y", "z", "x"], ["z", "0", "x"], ["x", "0", "1"]], [["y", "z", "x"], ["x", "z", "1"], ["z", "0", "1"]]]
    for niv in ordenes:
        r = call(T(tipo="iterada", f="1", niveles=niv))
        assert r["exact_result"] == "1/6"


def test_hoja19_ej6_suma_de_dos_piezas():
    a = call(T(tipo="triple_region", f="1", z_inf="0", z_sup="3", curvas=["y=x", "y=2*x", "y=1"], orden="dydx", punto=[0.5, 0.8]))
    b = call(T(tipo="triple_region", f="1", z_inf="0", z_sup="4-y^2", curvas=["y=x", "y=2*x", "y=1", "y=2"], orden="dydx", punto=[1, 1.5]))
    assert a["exact_result"] == "3/4" and b["exact_result"] == "9/8"  # suma 15/8
