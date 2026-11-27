"""Intérprete de enunciados en texto libre (calc3 tipo=auto): ejercicios de la hoja 20 y casos básicos."""
import re
import pytest
from math_universe_engine.dispatcher import handle


def _auto(t):
    return handle({"operation": "calc3", "params": {"tipo": "auto", "texto": t}, "latex": True, "steps": True, "timeout_ms": 60000})


def _num(r):
    return float(str(r["approximate_result"]).split("(")[0].replace("≈", "").strip().split()[0]) if False else None


EXACTOS = [
    ("Evalúe la integral doble ∬ cos((x−y)/(x+y)) dA donde R es el trapecio con vértices (1,0), (2,0), (0,2), (0,1)",
     0.5 * 3 * __import__("math").sin(1)),
    ("Calcular el área limitada por las curvas: y = x², y = 2x², y² = x, y² = 2x, utilizando la sustitución x² = u y y y² = v x",
     1 / 6),
    ("Calcular el área limitada por las curvas: xy = 1, xy = 2, xy³ = 1, xy³ = 2, en el primer cuadrante, mediante el siguiente cambio de variables: xy = u y xy³ = v",
     __import__("math").log(2) / 2),
    ("Determina el volumen de la región acotada por arriba por la superficie z = e^(xy) y por debajo por la región del plano xy acotada por las curvas y = x, y = x/2, y = 1/x, y = 2/x. Haga uso de una transformación para integrar en el plano uv",
     0.5 * __import__("math").log(2) * (__import__("math").e ** 2 - __import__("math").e)),
]


@pytest.mark.parametrize("texto,esperado", EXACTOS)
def test_enunciado_exacto(texto, esperado):
    r = _auto(texto)
    assert r["status"] == "success_exact", r.get("error") or r.get("warnings")
    assert r["verification"]["status"] == "passed"
    got = float(re.findall(r"-?\d+\.\d+", str(r["approximate_result"]))[0])
    assert got == pytest.approx(esperado, rel=1e-6)


def test_enunciado_centro_masa_cuadrante():
    r = _auto("Determine el centro de masa de la región R en el primer cuadrante acotada por las curvas x² + y² = 9, x² + y² = 16, y² − x² = 1, y² − x² = 9, si la densidad es proporcional al cuadrado de la distancia al origen")
    assert r["status"] in ("success_exact", "success_approximate")
    nums = [float(v) for v in re.findall(r"-?\d+\.\d+", str(r["approximate_result"]))]
    assert nums[-2] == pytest.approx(1.8143, abs=1e-3)
    assert nums[-1] == pytest.approx(2.9600, abs=1e-3)


def test_enunciado_no_reconocido_es_honesto():
    r = _auto("Escribe un poema sobre el mar")
    assert r["status"] != "success_exact"
