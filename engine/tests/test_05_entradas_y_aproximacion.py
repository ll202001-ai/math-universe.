"""Errores de entrada y aproximación numérica / precisión."""
import pytest
from conftest import call


@pytest.mark.parametrize("expr", ["", "   ", "2+", "(2+3", "2+3)", "*3", "2 $ 3", "2..3", "x y z )", "sin(", "2^", "()", "3 4 +"])
def test_sintaxis_invalida(expr):
    r = call(operation="evaluate", expression=expr)
    assert r["status"] == "invalid_input", r
    assert r["error"]["code"] in ("PARSE_ERROR", "INVALID_REQUEST")


def test_funcion_desconocida():
    assert call(operation="simplify", expression="foo(x)")["status"] == "unsupported"


def test_falta_expression_y_operacion_invalida():
    assert call(operation="simplify")["status"] == "invalid_input"
    assert call(operation="bogus", expression="1")["status"] == "invalid_input"


def test_campos_extra_rechazados_y_tipos():
    assert call(operation="evaluate", expression="1", foo=1)["status"] == "invalid_input"
    assert call(operation="evaluate", expression=5)["status"] == "invalid_input"
    assert call(operation="evaluate", expression="1", precision=0)["status"] == "invalid_input"
    assert call(operation="evaluate", expression="1", precision=5000)["status"] == "invalid_input"
    assert call(operation="evaluate", expression="1", timeout_ms=0)["status"] == "invalid_input"
    assert call(operation="evaluate", expression="1", assumptions={"x": "magico"})["status"] == "invalid_input"
    assert call(operation="solve", expression="x=1", variables=["1x"])["status"] == "invalid_input"


def test_version_incompatible_se_rechaza():
    r = call(operation="evaluate", expression="1", engine_version="9.0.0")
    assert r["status"] == "invalid_input" and r["error"]["code"] == "VERSION_MISMATCH"
    assert call(operation="evaluate", expression="1", engine_version="0.3.0")["status"] == "success_exact"


def test_ecuacion_mal_formada():
    assert call(operation="solve", expression="x==2")["status"] == "invalid_input"
    assert call(operation="solve", expression="x=1=2")["status"] == "invalid_input"
    assert call(operation="solve", expression="=2")["status"] == "invalid_input"


def test_variable_inexistente():
    assert call(operation="solve", expression="x+1=3", variables=["y"])["status"] == "invalid_input"
    r = call(operation="differentiate", expression="x^2+y", variables=["z"])
    assert r["status"] == "success_exact" and r["exact_result"] == "0" and any("no aparece" in w for w in r["warnings"])


def test_limite_sin_punto():
    assert call(operation="limit", expression="sin(x)/x")["status"] == "invalid_input"
    assert call(operation="limit", expression="x", point="abc")["status"] == "invalid_input"


def test_integral_con_un_solo_limite():
    assert call(operation="integrate", expression="x", lower="0")["status"] == "invalid_input"


def test_request_id_se_devuelve():
    assert call(operation="ping", request_id="abc-1")["request_id"] == "abc-1"
    assert call(operation="ping", request_id=42)["request_id"] == 42


# ---------------- aproximación ----------------
def test_aproximacion_respeta_precision_racional():
    r = call(operation="evaluate", expression="1/3", precision=10)
    assert r["approximate_result"] == "0.3333333333"
    r = call(operation="evaluate", expression="22/7", precision=50)
    assert r["approximate_result"] == "3.14285714285714285714285714285714285714285714285714"[:len(r["approximate_result"])]
    assert len(r["approximate_result"].split(".")[1]) == 50
    assert call(operation="evaluate", expression="1/7", precision=3)["approximate_result"] == "0.142"


def test_decimal_exacto_sin_aproximacion():
    r = call(operation="evaluate", expression="1/8")
    assert r["approximate_result"] == "0.125"


def test_irracionales_se_mantienen_exactos_y_aproximan_aparte():
    r = call(operation="evaluate", expression="sqrt(2)", precision=10)
    assert r["exact_result"] == "sqrt(2)" and r["approximate_result"] == "1.414213562"


def test_precision_mayor_a_15_en_trascendente_advierte():
    # 0.5.0: con mpmath, pi/e/sin(1)... tienen cifras arbitrarias (contrastadas en coma flotante; test_23).
    # Sin mpmath se sigue advirtiendo y se dan ~15 cifras (cubierto en test_23 con mpmath desactivado).
    r = call(operation="evaluate", expression="pi", precision=40)
    try:
        import mpmath  # noqa: F401
    except ImportError:
        assert any("15 cifras" in w for w in r["warnings"]) and len(r["approximate_result"].replace(".", "")) <= 15
    else:
        assert r["approximate_result"] == "3.141592653589793238462643383279502884197" and r["warnings"] == []


def test_precision_mayor_a_15_en_radical_es_exacta():
    r = call(operation="evaluate", expression="sqrt(2)", precision=40)
    assert r["approximate_result"] == "1.414213562373095048801688724209698078570" and r["warnings"] == []


def test_pi_y_e_son_constantes():
    r = call(operation="evaluate", expression="pi+1")
    assert r["exact_result"] == "pi + 1" and r["approximate_result"].startswith("4.14159265")
    assert call(operation="evaluate", expression="e^0")["exact_result"] == "1"


def test_integral_definida_aproxima_y_verifica_con_simpson():
    r = call(operation="integrate", expression="1/x", lower="1", upper="2", precision=8)
    assert r["exact_result"].replace(" ", "") in ("ln(2)", "ln(2)-ln(1)") or "ln(2)" in r["exact_result"]
    assert r["approximate_result"].startswith("0.6931471")
    assert r["verification"]["status"] == "passed"


def test_resultado_aproximado_nunca_se_etiqueta_exacto():
    r = call(operation="evaluate", expression="1/3")
    assert r["status"] == "success_exact" and r["exact_result"] == "1/3"
    assert r["approximate_result"] != r["exact_result"]
