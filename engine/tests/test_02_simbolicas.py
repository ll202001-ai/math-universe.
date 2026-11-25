"""Simplificación, expansión, factorización, derivadas, integrales y límites."""
import re, pytest
from conftest import call


def norm(s): return re.sub(r"\s+", "", s)


@pytest.mark.parametrize("expr,exp", [
    ("(x+1)^3", "x^3+3*x^2+3*x+1"), ("(x-1)*(x+1)", "x^2-1"), ("(a+b)^2", "a^2+2*a*b+b^2"),
    ("(x+y)*(x-y)", "x^2-y^2"), ("(2x+3)^2", "4*x^2+12*x+9"),
])
def test_expand(expr, exp):
    r = call(operation="expand", expression=expr)
    assert r["status"] == "success_exact" and norm(r["exact_result"]) == exp and r["verification"]["status"] == "passed"


@pytest.mark.parametrize("expr,exp", [
    ("x^2-5x+6", "(x-3)*(x-2)"), ("x^2-9", "(x-3)*(x+3)"), ("x^3-1", "(x-1)*(x^2+x+1)"),
    ("2x^2-2", "2*(x-1)*(x+1)"), ("x^4-1", "(x-1)*(x+1)*(x^2+1)"), ("x^4+4", "(x^2-2*x+2)*(x^2+2*x+2)"),
    ("x^2+2x+1", "(x+1)^2"), ("x^3-6x^2+11x-6", "(x-3)*(x-2)*(x-1)"),
    ("6x^2+5x+1", "(2*x+1)*(3*x+1)"),
])
def test_factor(expr, exp):
    r = call(operation="factor", expression=expr)
    assert r["status"] == "success_exact", r
    # compara como conjunto de factores (el orden no es relevante)
    f = lambda s: sorted(re.findall(r"\([^()]*\)(?:\^\d)?|[-\d]+\*?", norm(s)))
    assert f(r["exact_result"]) == f(exp), (r["exact_result"], exp)
    assert r["verification"]["status"] == "passed"


def test_factor_enunciado_pdf_x2_5x_6_se_reexpande():
    r = call(operation="factor", expression="x^2-5x+6")
    back = call(operation="expand", expression=r["exact_result"])
    assert norm(back["exact_result"]) == "x^2-5*x+6"


@pytest.mark.parametrize("expr,exp", [
    ("x^3*sin(x)", "x^3*cos(x)+3*x^2*sin(x)"), ("x^2", "2*x"), ("e^(2x)", "2*exp(2*x)"),
    ("ln(x)", "1/x"), ("1/x", "-1/x^2"), ("sin(x)*cos(x)", "cos(x)^2-sin(x)^2"),
    ("x^5-3x^2+7", "5*x^4-6*x"),
])
def test_derivative(expr, exp):
    r = call(operation="differentiate", expression=expr)
    assert r["status"] == "success_exact", r
    assert r["verification"]["status"] == "passed"
    # equivalencia con el esperado en puntos de prueba (sin depender del orden de los términos)
    from math_universe_engine.verify import equivalent
    from math_universe_engine.ast_tools import normalize
    from math_universe_engine.parser import parse
    assert equivalent(normalize(parse(exp)), r["exact_result"]) == "passed"


def test_derivative_orden_superior():
    r = call(operation="differentiate", expression="x^4", order=2)
    assert norm(r["exact_result"]) == "12*x^2"


@pytest.mark.parametrize("expr", [
    "x^2", "x^3-2x+1", "1/x", "1/x^2", "sin(x)", "cos(2x)", "e^x", "e^(3x)", "x*e^x", "x^2*e^x", "x*sin(x)", "x^2*cos(x)",
    "1/(x^2-1)", "1/(x^2+1)", "(x+3)/(x^2+2x+5)", "x^3/(x-1)", "1/(x^2-2)", "(2x+1)/((x-1)*(x-2))", "1/(x-1)^2", "x*ln(x)",
])
def test_integral_indefinida_con_constante_y_verificacion(expr):
    r = call(operation="integrate", expression=expr)
    assert r["status"] == "success_exact", r
    assert r["exact_result"].endswith("+ C")
    assert r["verification"]["status"] == "passed", r["verification"]


def test_integral_x2_enunciado_pdf():
    r = call(operation="integrate", expression="x^2")
    assert norm(r["exact_result"]) == "(1/3)*x^3+C"


@pytest.mark.parametrize("expr,lo,hi,exp", [("x^2", "0", "3", "9"), ("1/x^2", "1", "2", "1/2"), ("e^x", "0", "1", "exp(1) - 1")])
def test_integral_definida(expr, lo, hi, exp):
    r = call(operation="integrate", expression=expr, lower=lo, upper=hi)
    assert r["status"] == "success_exact" and r["verification"]["status"] == "passed"
    assert norm(r["exact_result"]) == norm(exp)


@pytest.mark.parametrize("expr,pt,exp", [
    ("sin(x)/x", "0", "1"), ("(x^2-1)/(x-1)", "1", "2"), ("(1-cos(x))/x^2", "0", "1/2"), ("(e^x-1)/x", "0", "1"),
    ("(x-sin(x))/x^3", "0", "1/6"), ("(2x^2+1)/(x^2-3)", "oo", "2"), ("(3x+1)/(x-5)", "-oo", "3"),
    ("1/x^2", "0", "oo"), ("tan(x)/x", "0", "1"), ("(x^3-8)/(x-2)", "2", "12"), ("(sqrt(x+4)-2)/x", "0", "1/4"),
])
def test_limites(expr, pt, exp):
    r = call(operation="limit", expression=expr, point=pt)
    assert r["status"] == "success_exact", r
    assert r["exact_result"] == exp and r["verification"]["status"] == "passed", r


def test_limite_sin_x_sobre_x_enunciado_pdf():
    assert call(operation="limit", expression="sin(x)/x", point="0")["exact_result"] == "1"


def test_limites_laterales_distintos():
    r = call(operation="limit", expression="1/x", point="0")
    assert r["status"] == "no_solution"
    assert call(operation="limit", expression="1/x", point="0", direction="+")["exact_result"] == "oo"
    assert call(operation="limit", expression="1/x", point="0", direction="-")["exact_result"] == "-oo"
