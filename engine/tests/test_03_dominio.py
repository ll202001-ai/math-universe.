"""Restricciones de dominio y supuestos."""
import pytest
from conftest import call


def test_pdf_x2_menos_1_sobre_x_menos_1():
    r = call(operation="simplify", expression="(x^2-1)/(x-1)")
    assert r["exact_result"] == "x + 1"
    assert "x ≠ 1" in r["conditions"]
    assert r["verification"]["status"] == "passed"


@pytest.mark.parametrize("expr,res,cond", [
    ("x/x", "1", "x ≠ 0"),
    ("(x^2-4)/(x+2)", "x - 2", "x ≠ -2"),
    ("(x^2-3x+2)/(x^2-1)", "(x - 2)/(x + 1)", "x ≠ 1"),
    ("(x^2-3x+2)/(x^2-1)", "(x - 2)/(x + 1)", "x ≠ -1"),
    ("(x^3-x)/(x^2-x)", "x + 1", "x ≠ 0"),
    ("1/x+1/(x+1)", "(2*x + 1)/(x^2 + x)", "x ≠ -1"),
    ("(x*y)/(x*z)", "y/z", "x ≠ 0"),
    ("(x*y)/(x*z)", "y/z", "z ≠ 0"),
    ("(x^2-y^2)/(x-y)", "x + y", "x - y ≠ 0"),
])
def test_condiciones_conservadas(expr, res, cond):
    r = call(operation="simplify", expression=expr)
    assert r["exact_result"] == res and cond in r["conditions"], r
    assert r["verification"]["status"] == "passed"


def test_condicion_de_denominador_oculto_en_potencia_negativa():
    r = call(operation="simplify", expression="(x^2-1)*(x-1)^(-1)")
    assert r["exact_result"] == "x + 1" and "x ≠ 1" in r["conditions"]


def test_sqrt_x2_es_abs_x_sin_supuestos():
    r = call(operation="simplify", expression="sqrt(x^2)")
    assert r["exact_result"] == "abs(x)"


def test_sqrt_x2_es_x_con_x_positiva():
    r = call(operation="simplify", expression="sqrt(x^2)", assumptions={"x": "positive"})
    assert r["exact_result"] == "x"


def test_sqrt_x2_es_menos_x_con_x_negativa():
    assert call(operation="simplify", expression="sqrt(x^2)", assumptions={"x": "negative"})["exact_result"] == "-x"


def test_supuesto_no_nulo_elimina_condicion_redundante():
    r = call(operation="simplify", expression="x/x", assumptions={"x": "positive"})
    assert r["exact_result"] == "1" and r["conditions"] == []


def test_supuesto_positivo_descarta_condicion_x_distinto_de_menos_1():
    r = call(operation="simplify", expression="(x^2-1)/(x+1)", assumptions={"x": "positive"})
    assert r["exact_result"] == "x - 1" and r["conditions"] == []


def test_supuesto_positivo_no_descarta_x_distinto_de_1():
    r = call(operation="simplify", expression="(x^2-1)/(x-1)", assumptions={"x": "positive"})
    assert "x ≠ 1" in r["conditions"]


def test_logaritmo_registra_dominio():
    r = call(operation="simplify", expression="ln(x)+ln(x)")
    assert "x > 0" in r["conditions"]


def test_raiz_registra_dominio():
    assert "x + 1 >= 0" in call(operation="simplify", expression="sqrt(x+1)")["conditions"]


def test_cero_a_la_cero_y_division_por_cero():
    assert call(operation="simplify", expression="0^0")["status"] == "domain_error"
    assert call(operation="simplify", expression="1/0")["status"] == "domain_error"
    assert call(operation="simplify", expression="x/0")["status"] == "domain_error"


def test_ecuacion_raiz_extrana_excluida():
    r = call(operation="solve", expression="(x^2-1)/(x-1)=0")
    assert r["exact_result"] == "x = -1" and "x ≠ 1" in r["conditions"]
    assert any("x = 1 excluida" in w for w in r["warnings"])


def test_ecuacion_unica_raiz_prohibida_no_tiene_solucion():
    r = call(operation="solve", expression="x/(x-2)=2/(x-2)")
    assert r["status"] == "no_solution" and any("x = 2 excluida" in w for w in r["warnings"])


def test_1_sobre_x_igual_0_no_tiene_solucion():
    assert call(operation="solve", expression="1/x=0")["status"] == "no_solution"


def test_despeje_conserva_condicion_del_divisor():
    r = call(operation="solve", expression="V=I*R", variables=["R"])
    assert r["exact_result"] == "R = V/I" and "I ≠ 0" in r["conditions"]
    assert r["verification"]["status"] == "passed"


def test_despeje_con_supuesto_I_no_nula_quita_condicion():
    r = call(operation="solve", expression="V=I*R", variables=["R"], assumptions={"I": "nonzero"})
    assert r["conditions"] == []


def test_supuesto_sobre_variable_ausente_se_avisa():
    r = call(operation="simplify", expression="x+1", assumptions={"q": "positive"})
    assert any("'q'" in w for w in r["warnings"])


def test_supuestos_en_soluciones():
    r = call(operation="solve", expression="x^2-4=0", assumptions={"x": "positive"})
    assert r["exact_result"] == "x = 2"
    r = call(operation="solve", expression="x^2-4=0", assumptions={"x": "negative"})
    assert r["exact_result"] == "x = -2"
    assert call(operation="solve", expression="x^2+4=0")["status"] == "no_solution"
    assert call(operation="solve", expression="x^2+4=0", assumptions={"x": "complex"})["exact_result"] == "x = 2*i, x = -2*i"
    assert call(operation="solve", expression="2x-1=0", assumptions={"x": "integer"})["status"] == "no_solution"
