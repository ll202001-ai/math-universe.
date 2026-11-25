"""Prueba el CABLEADO del respaldo SymPy (verificación independiente del resultado externo) con un backend SIMULADO.
No ejecuta SymPy: comprueba que un resultado externo correcto se verifica, y que uno incorrecto se rechaza."""
import pytest
from conftest import call
from math_universe_engine import symbolic, limits


@pytest.fixture
def falso(monkeypatch):
    def activar(salida):
        monkeypatch.setattr(symbolic, "available", lambda: True)
        monkeypatch.setattr(symbolic, "run", lambda op, ast, variables: salida)
        # el proceso hijo real no puede ver el parche: se ejecuta en línea (el proceso hijo se prueba en test_06 y test_08)
        monkeypatch.setattr(limits, "run_hard_timeout", lambda fn, args, t: fn(*args))
    return activar


def test_primitiva_externa_correcta_se_verifica(falso):
    falso("x/2 - sin(2*x)/4 + C")                        # ∫ sin(x)^2 dx
    r = call(operation="integrate", expression="sin(x)^2", variables=["x"])
    assert r["status"] == "success_exact" and r["method"] == "sympy_respaldo_experimental"
    assert r["verification"]["status"] == "passed"


def test_primitiva_externa_incorrecta_se_rechaza(falso):
    falso("x/2 + sin(2*x)/4 + C")                        # signo equivocado
    r = call(operation="integrate", expression="sin(x)^2", variables=["x"])
    assert r["status"] == "internal_error" and r["error"]["code"] == "VERIFICATION_FAILED"
    assert r["error"]["details"]["unverified_result"].startswith("x/2 + sin")


def test_resultado_externo_no_evaluable_nunca_es_passed(falso):
    falso("x + 2")
    r = call(operation="simplify", expression="foo(x)")        # función desconocida: no hay forma de comprobar
    assert r["verification"]["status"] != "passed"


def test_integral_externa_no_evaluable_nunca_es_passed(falso):
    falso("x^2/2 + C")
    r = call(operation="integrate", expression="gamma(x)", variables=["x"])     # función que el motor no puede evaluar ni derivar
    assert r["verification"]["status"] != "passed"


def test_texto_de_sympy_se_traduce():
    assert symbolic.from_sympy_text("Abs(x)**2 + log(E) + I") == "abs(x)^2 + ln(e) + i"


def test_interruptor_de_entorno(monkeypatch):
    monkeypatch.setenv("MATH_UNIVERSE_DISABLE_SYMPY", "1")
    assert symbolic.available() is False
