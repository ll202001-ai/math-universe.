"""Entrada universal (operación `resolver`): texto libre -> intención -> motor -> verificación.
Los oráculos son independientes (diferencias finitas, cuadratura, derivación inversa, fórmulas cerradas)."""
import math
import re
import pytest
from math_universe_engine.dispatcher import handle

try:
    import sympy  # noqa: F401
    HAY_SYMPY = True
except Exception:  # pragma: no cover
    HAY_SYMPY = False

needs_sympy = pytest.mark.skipif(not HAY_SYMPY, reason="requiere sympy (se ejecuta en CI/app)")


def R(texto):
    return handle({"operation": "resolver", "expression": texto, "latex": True, "steps": True, "timeout_ms": 60000})


def nums(r):
    return [float(x) for x in re.findall(r"-?\d+\.?\d*(?:e-?\d+)?", str(r.get("approximate_result") or r.get("exact_result")))]


def test_derivada_por_diferencias_finitas():
    r = R("deriva x^3*sin(x)")
    assert r["status"] == "success_exact"
    f = lambda x: x**3 * math.sin(x)
    g = lambda x: eval(r["exact_result"].replace("^", "**"), {"sin": math.sin, "cos": math.cos, "x": x})
    for x in (0.3, 1.1, 2.0):
        h = 1e-6
        assert abs((f(x + h) - f(x - h)) / (2 * h) - g(x)) < 1e-5


def test_integral_definida_gaussiana_numerica():
    r = R("integral de e^(-x^2) dx de 0 a 1")
    assert r["status"] in ("success_exact", "success_approximate")
    assert abs(nums(r)[0] - 0.7468241328) < 1e-6


def test_integral_x_exp_x_derivacion_inversa():
    r = R("integral de x*e^x dx")
    assert r["status"] == "success_exact"
    F = lambda x: eval(re.sub(r"\s*\+\s*C$", "", r["exact_result"]).replace("^", "**"), {"exp": math.exp, "x": x})
    h = 1e-6
    for x in (0.2, 0.9):
        assert abs((F(x + h) - F(x - h)) / (2 * h) - x * math.exp(x)) < 1e-5


def test_ecuacion_trascendente_raiz_numerica():
    r = R("resuelve cos(x)=x")
    assert r["status"] in ("success_exact", "success_approximate")
    assert any(abs(v - 0.7390851332) < 1e-6 for v in nums(r))


def test_area_entre_curvas():
    r = R("área entre y=x^2 y y=x")
    assert abs(nums(r)[0] - 1 / 6) < 1e-6 or "1/6" in str(r.get("exact_result"))


def test_volumen_paraboloide_enruta_a_calc3():
    r = R("volumen del sólido bajo z=4-x^2-y^2 sobre el disco x^2+y^2<=4")
    assert r["status"] == "success_exact"
    assert abs(nums(r)[0] - 8 * math.pi) < 1e-4


def test_divergencia_campo():
    r = R("divergencia de F=(x*y, y*z, z*x)")
    assert r["status"] == "success_exact"
    assert "x" in r["exact_result"] and "y" in r["exact_result"] and "z" in r["exact_result"]


def test_texto_sin_sentido_no_inventa():
    r = R("cuéntame un chiste")
    assert r["status"] in ("unsupported", "invalid_input")
    assert not r.get("exact_result")


@needs_sympy
def test_limite_notable():
    r = R("límite de sin(x)/x cuando x tiende a 0")
    assert r["status"] == "success_exact" and "1" in str(r["exact_result"])


@needs_sympy
def test_determinante():
    r = R("determinante de [[1,2],[3,4]]")
    assert r["status"] == "success_exact" and "-2" in str(r["exact_result"])
