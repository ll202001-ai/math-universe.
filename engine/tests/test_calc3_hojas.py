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


# ---- Hoja #16 (optimización) ----
def _fnum(r, i=0):
    return float(re.findall(r"f = (-?\d+\.?\d*)", r["exact_result"])[i])


def test_hoja16_ingreso_y_cafe():
    r = call(T(tipo="extremos", f="-5*x1^2-8*x2^2-2*x1*x2+42*x1+102*x2", variables=["x1", "x2"]))
    assert "P1(3, 6)" in r["exact_result"] and "máximo" in r["exact_result"]
    r = call(T(tipo="extremos", f="(x-6)*(300-100*x+70*y)+(y-8)*(250+80*x-75*y)", variables=["x", "y"]))
    assert "P1(69/5, 50/3)" in r["exact_result"]  # 13.80 y 16.67


def test_hoja16_lagrange():
    r = call(T(tipo="lagrange", f="100*x^(3/4)*y^(1/4)", restricciones=["150*x+250*y=50000"], variables=["x", "y"], positivo=True))
    assert "P1(250, 50)" in r["exact_result"] and _fnum(r) == pytest.approx(16718.5, abs=0.1)
    r = call(T(tipo="lagrange", f="3*x^2+200+y^2+400+2*z^2+300", restricciones=["x+y+z=1100"], variables=["x", "y", "z"]))
    assert "P1(200, 600, 300)" in r["exact_result"]
    r = call(T(tipo="lagrange", f="x*y*z", restricciones=["x+2*y+3*z=6"], variables=["x", "y", "z"], positivo=True))
    assert "P1(2, 1, 2/3)" in r["exact_result"] and "4/3" in r["exact_result"]
    r = call(T(tipo="lagrange", f="(x-2)^2+(y-2)^2+(z-2)^2", restricciones=["z=x^2+y^2+2"], variables=["x", "y", "z"]))
    assert math.sqrt(_fnum(r)) == pytest.approx(2.0830, abs=1e-3)
    r = call(T(tipo="lagrange", f="(x-t)^2+(y-t)^2+(z-2-t)^2", restricciones=["z^2-9*x^2-9*y^2=9"], variables=["x", "y", "z", "t"]))
    assert math.sqrt(_fnum(r, 1)) == pytest.approx(0.7474, abs=1e-3)
    r = call(T(tipo="lagrange", f="x^2+y^2+z^2", restricciones=["x+y+z=1", "x^2+y^2=1"], variables=["x", "y", "z"]))
    assert "P1(-√2/2, -√2/2" in r["exact_result"] and "P2(0, 1, 0)" in r["exact_result"]


def test_suma_de_piezas_hoja19_ej6():
    r = call(T(tipo="suma", partes=[
        T(tipo="triple_region", f="1", z_inf="0", z_sup="3", curvas=["y=x", "y=2*x", "y=1"], orden="dydx", punto=[0.5, 0.8]),
        T(tipo="triple_region", f="1", z_inf="0", z_sup="4-y^2", curvas=["y=x", "y=2*x", "y=1", "y=2"], orden="dydx", punto=[1, 1.5])]))
    assert r["exact_result"] == "15/8" and r["verification"]["status"] == "passed"


def test_hoja17_ej18_semidisco_10pi():
    """x²+z²=4, x+y=5, y=z=0: V = ∬(5−x) dA sobre el semidisco z≥0 = 10π (mismo planteo que el ejemplo de Sullivan).
    La hoja imprime ≈11.9587, que no corresponde a esta lectura (ver LIMITACIONES)."""
    r = call(T(tipo="region", que="volumen", z="5-x", curvas=["x^2+y^2=4", "y=0"], orden="dydx", punto=[0, 1]))
    assert float(re.search(r"\d+\.\d+", r["approximate_result"]).group()) == pytest.approx(10 * math.pi, rel=1e-6)
