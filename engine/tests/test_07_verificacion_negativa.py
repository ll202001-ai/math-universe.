"""La verificación independiente debe DETECTAR resultados incorrectos (si no, no vale nada)."""
import pytest
from conftest import call
from math_universe_engine import calculus, solve as S
from math_universe_engine.ast_tools import normalize
from math_universe_engine.parser import parse
from math_universe_engine.verify import equivalent
from fractions import Fraction


def A(s): return normalize(parse(s))


def test_equivalencia_detecta_error():
    assert equivalent(A("(x^2-1)/(x-1)"), "x+2") == "failed"
    assert equivalent(A("(x^2-1)/(x-1)"), "x+1") == "passed"
    assert equivalent(A("sqrt(x^2)"), "x") == "failed"            # sin supuestos es |x|, no x
    assert equivalent(A("sqrt(x^2)"), "abs(x)") == "passed"


def test_derivada_incorrecta_es_detectada():
    assert calculus.verify_derivative(A("x^3"), "x", A("2*x^2")) == "failed"
    assert calculus.verify_derivative(A("x^3"), "x", A("3*x^2")) == "passed"


def test_primitiva_incorrecta_es_detectada():
    assert calculus.verify_antiderivative(A("x^2"), "x", A("x^3/2")) == "failed"
    assert calculus.verify_antiderivative(A("x^2"), "x", A("x^3/3")) == "passed"


def test_limite_incorrecto_es_detectado():
    assert calculus.verify_limit(A("sin(x)/x"), "x", Fraction(0), {"kind": "finite", "value": Fraction(2)}) == "failed"
    assert calculus.verify_limit(A("sin(x)/x"), "x", Fraction(0), {"kind": "finite", "value": Fraction(1)}) == "passed"


def test_sistema_con_solucion_incorrecta_es_detectado():
    from math_universe_engine.poly import Poly
    eqs, vs, Am, b = S.linear_system(["2x+y=5", "x-y=1"])
    bad = {"x": Poly.const(3), "y": Poly.const(1)}
    good = {"x": Poly.const(2), "y": Poly.const(1)}
    assert S.verify_linear("unique", eqs, vs, bad) == "failed"
    assert S.verify_linear("unique", eqs, vs, good) == "passed"


def test_despeje_incorrecto_es_detectado():
    l, r = S.split_equation("V=I*R")
    assert S.verify_isolate(l, r, "R", A("V*I"), {}) == "failed"
    assert S.verify_isolate(l, r, "R", A("V/I"), {}) == "passed"


def test_un_resultado_que_falla_la_verificacion_no_se_entrega(monkeypatch):
    real = calculus.differentiate
    monkeypatch.setattr(calculus, "differentiate", lambda ast, var, order=1: A("2*x"))   # derivada errónea de x^3
    r = call(operation="differentiate", expression="x^3")
    assert r["status"] == "internal_error" and r["error"]["code"] == "VERIFICATION_FAILED"
    assert r["exact_result"] is None if "exact_result" in r else True
    assert r["error"]["details"]["unverified_result"] == "2*x"


def test_nunca_se_marca_passed_sin_comprobacion():
    # operaciones sin segunda vía deben declararlo
    assert call(operation="evaluate", expression="gcd(12,18)")["verification"]["status"] == "not_possible"
    assert call(operation="parse", expression="x+1")["verification"]["status"] == "not_performed"
    assert call(operation="ping")["verification"]["status"] == "not_performed"
    assert call(operation="solve", expression="x^2+1=0")["verification"]["status"] != "passed"
