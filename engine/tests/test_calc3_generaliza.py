"""Ejercicios NUEVOS (no pertenecen a las guías) para comprobar que el intérprete generaliza.
Cada oráculo se calculó por un camino independiente (fórmulas cerradas conocidas o cuadratura)."""
import math
import re
import pytest
from math_universe_engine.dispatcher import handle

PI = math.pi


def _auto(t):
    return handle({"operation": "calc3", "params": {"tipo": "auto", "texto": t}, "latex": True, "steps": True, "timeout_ms": 60000})


def _nums(r):
    return [float(x) for x in re.findall(r"-?\d+\.?\d*(?:e-?\d+)?", str(r.get("approximate_result")))]


NUMERICOS = [
    ("Calcule la integral doble de x²+y² sobre la región x²+y² ≤ 4, x ≥ 0", 4 * PI),
    ("Halle el volumen de la esfera x²+y²+z²=9", 36 * PI),
    ("Calcule el volumen del sólido limitado por los paraboloides z = x²+y² y z = 8 − x² − y²", 16 * PI),
    ("Halle la masa de una lámina triangular con vértices (0,0), (2,0), (0,2) y densidad ρ(x,y)=x+y", 8 / 3),
    ("Evalúe ∫_0^1 ∫_x^1 e^(y²) dy dx", (math.e - 1) / 2),
    ("Calcule el volumen del tetraedro limitado por los planos coordenados y x+y+z=1", 1 / 6),
    ("Evalúe la integral triple de z dV sobre el cilindro x²+y² ≤ 1, 0 ≤ z ≤ 2", 2 * PI),
    ("Halle el centroide de la región semicircular y ≥ 0, x²+y² ≤ 1", 4 / (3 * PI)),
    ("Halle el momento de inercia respecto al eje z de un disco homogéneo de densidad 1 y radio 2: x²+y² ≤ 4", 8 * PI),
    ("Calcule el volumen del elipsoide x²/4 + y²/9 + z² = 1", 8 * PI),
    ("Calcule el volumen del elipsoide x²/4 + y²/9 + z² ≤ 1", 8 * PI),
    ("Halle el área de la región limitada por y = x y y = x²", 1 / 6),
    ("Calcule el área de la elipse x²/9 + y²/4 = 1", 6 * PI),
    ("Calcule el volumen del sólido dentro de la esfera x²+y²+z² = 4 y sobre el cono z = sqrt(x²+y²)", 8 * PI * (2 - math.sqrt(2)) / 3),
    ("Calcule el área de la superficie z = x² + y² que queda bajo el plano z = 4", PI / 6 * (17 * math.sqrt(17) - 1)),
    ("Calcule el trabajo del campo F = (−y, x) a lo largo de la circunferencia x²+y²=1 recorrida una vez en sentido antihorario", 2 * PI),
    ("Calcule ∬ (x + y)² dA sobre la región |x| + |y| ≤ 1", 2 / 3),
    ("Halle el volumen del sólido bajo z = 4 − x² − y² sobre el plano xy", 8 * PI),
    ("Evalúe ∬ x y dA sobre la región acotada por y = x, y = 2x, x = 1, x = 2", 45 / 8),
    ("Evalúe ∬ x² dA sobre la región (x−1)²/9 + (y−2)²/4 ≤ 1", 39 * PI / 2),
    ("Halle el área de la región (x-1)² + (y+2)² ≤ 5", 5 * PI),
    ("Calcule la distancia mínima del origen al plano x + 2y + 3z = 14", math.sqrt(14)),
    ("Calcule el flujo del campo F = (x, y, z) a través de la esfera x²+y²+z²=4", 4 / 3 * PI * 8 * 3),
    ("Calcule el trabajo del campo F = (x*y, x²) a lo largo de la curva y = x² desde (0,0) hasta (1,1)", 3 / 4),
]


@pytest.mark.parametrize("texto,esperado", NUMERICOS)
def test_generaliza_numerico(texto, esperado):
    r = _auto(texto)
    assert r["status"] in ("success_exact", "success_approximate"), r.get("error")
    assert any(abs(n - esperado) <= 1e-5 * max(1, abs(esperado)) for n in _nums(r)), (r.get("approximate_result"), esperado)


TEXTUALES = [
    ("Halle los puntos críticos de f(x,y) = x³ − 3x + y² y clasifíquelos", ["P1(-1, 0)", "silla", "P2(1, 0)", "mínimo"]),
    ("Maximice f(x,y,z)=xyz sujeto a x+y+z=6, con x,y,z>0", ["P1(2, 2, 2)", "f = 8"]),
    ("Calcule el jacobiano de x = r cos θ, y = r sin θ", ["r"]),
    ("Calcule el rotacional del campo F = (yz, xz, xy)", ["(0, 0, 0)"]),
    ("Calcule la divergencia del campo F = (x², y², z²)", ["2*x + 2*y + 2*z"]),
    ("Calcule el gradiente de f(x,y,z) = x²y + z³", ["(2*x*y, x^2, 3*z^2)"]),
    ("Determine si el campo F = (2xy, x² + 3y²) es conservativo y halle su función potencial", ["y^3", "x^2*y"]),
    ("Calcule el laplaciano de f(x,y,z) = x² + y² + z²", ["6"]),
]


@pytest.mark.parametrize("texto,partes", TEXTUALES)
def test_generaliza_textual(texto, partes):
    r = _auto(texto)
    assert r["status"] == "success_exact", r.get("error")
    for p in partes:
        assert p in (r.get("exact_result") or ""), (r.get("exact_result"), p)


def test_no_devuelve_exacto_incorrecto_si_se_ignora_una_restriccion():
    """regresión: antes devolvía π (media región) para x ≥ 0 ignorado; ahora o acierta o se niega"""
    r = _auto("Calcule la integral doble de x²+y² sobre la región x²+y² ≤ 4, x ≥ 0")
    if r["status"] == "success_exact":
        assert abs(_nums(r)[0] - 4 * PI) < 1e-6
