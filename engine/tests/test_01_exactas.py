"""Casos exactos: aritmética racional y radicales."""
import pytest
from conftest import call

CASES = [
    ("2+3*5", "17"), ("(2+3)*5", "25"), ("2^3^2", "512"), ("-2^2", "-4"), ("2^-2", "1/4"),
    ("1/3+1/6", "1/2"), ("0.1+0.2", "3/10"), ("1e3", "1000"), ("2(3+4)", "14"), ("10/4", "5/2"),
    ("5!", "120"), ("sqrt(16)", "4"), ("sqrt(9/4)", "3/2"), ("gcd(12,18)", "6"), ("lcm(4,6)", "12"),
    ("mod(17,5)", "2"), ("8^(1/3)", "2"), ("abs(-7/2)", "7/2"), ("2**10", "1024"), ("floor(7/2)", "3"),
    ("ceil(-7/2)", "-3"), ("(1/2)^10", "1/1024"), ("100!/98!", "9900"),
    ("sqrt(8)", "2*sqrt(2)"), ("sqrt(8)+sqrt(2)", "3*sqrt(2)"), ("sqrt(1/2)", "(1/2)*sqrt(2)"),
    ("sqrt(12)*sqrt(3)", "6"), ("(sqrt(2))^2", "2"),
]


@pytest.mark.parametrize("expr,exp", CASES)
def test_exact(expr, exp):
    r = call(operation="evaluate", expression=expr)
    assert r["status"] == "success_exact", r
    assert r["exact_result"] == exp
    if any(f in expr for f in ("gcd", "lcm", "mod", "floor", "ceil")):
        # sin segunda vía independiente para estas funciones: el motor lo declara en lugar de afirmar «verificado»
        assert r["verification"]["status"] == "not_possible"
    else:
        assert r["verification"]["status"] == "passed"


def test_enunciado_pdf_1_3_mas_1_6():
    assert call(operation="evaluate", expression="1/3+1/6")["exact_result"] == "1/2"


def test_exacto_no_se_convierte_a_decimal():
    r = call(operation="evaluate", expression="1/3")
    assert r["exact_result"] == "1/3" and r["approximate_result"].startswith("0.3333")
    assert any("aproximación" in w for w in r["warnings"])
