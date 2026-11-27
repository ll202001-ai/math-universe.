"""Motor 0.7.0: funciones especiales, %, log en base b, sumatorias/productorias, sustitución, matrices simbólicas,
lógica, conjuntos y derivación implícita. Valores de referencia conocidos a mano; verificaciones saboteadas."""
import pytest

from conftest import call
from math_universe_engine import advanced2

pytest.importorskip("sympy")
pytest.importorskip("mpmath")


@pytest.fixture(autouse=True)
def _sympy_activo(monkeypatch):
    monkeypatch.delenv("MATH_UNIVERSE_DISABLE_SYMPY", raising=False)   # el respaldo de evaluate usa SymPy


def ok(r):
    assert r["status"] == "success_exact", r
    assert r["verification"]["status"] == "passed", r
    return r


@pytest.mark.parametrize("expr, exacto", [
    ("50%", "1/2"), ("20% * 150", "30"), ("gamma(5)", "24"), ("gamma(1/2)", "sqrt(pi)"), ("erf(0)", "0"),
    ("log(8,2)", "3"), ("sec(0)", "1"), ("cbrt(-8)", "-2"), ("beta(2,3)", "1/12"), ("zeta(2)", "pi^2/6"),
])
def test_funciones_y_porcentaje(expr, exacto):
    assert ok(call(operation="evaluate", expression=expr))["exact_result"] == exacto


def test_respaldo_de_evaluate_da_aproximacion():
    assert ok(call(operation="evaluate", expression="gamma(1/2)"))["approximate_result"].startswith("1.7724538509")


def test_funcion_fuera_de_dominio():
    r = call(operation="evaluate", expression="log(8,1)")                 # SymPy da zoo: no es un resultado
    assert r["status"] == "domain_error" and r.get("exact_result") is None


def test_simplificacion_con_funciones_nuevas():
    assert ok(call(operation="simplify", expression="gamma(x+1)/gamma(x)"))["exact_result"] == "x"
    assert ok(call(operation="simplify", expression="sec(x)*cos(x)"))["exact_result"] == "1"


# ---------------- Σ y Π
def S(expr, frm, to, op="sum", var="k"):
    return call(operation=op, expression=expr, params={"var": var, "from": frm, "to": to})


def test_suma_finita():
    assert ok(S("k", "1", "10"))["exact_result"] == "55"


def test_suma_con_limite_simbolico():
    r = ok(S("k", "1", "n"))
    assert r["exact_result"].replace(" ", "") in ("n*(n+1)/2", "n*(n + 1)/2".replace(" ", ""))


def test_serie_de_basilea():
    r = ok(S("1/k^2", "1", "oo"))
    assert r["exact_result"] == "pi^2/6" and r["approximate_result"].startswith("1.6449340668")


def test_serie_geometrica():
    assert ok(S("(1/2)^k", "0", "oo"))["exact_result"] == "2"


def test_serie_armonica_diverge():
    r = call(operation="sum", expression="1/k", params={"var": "k", "from": "1", "to": "oo"})
    assert r["exact_result"] == "diverge" and r["verification"]["status"] == "not_possible"


def test_productoria():
    assert ok(S("k", "1", "5", op="product"))["exact_result"] == "120"


def test_suma_saboteada_no_se_entrega(monkeypatch):
    import sympy as sp
    monkeypatch.setattr(sp, "summation", lambda *a, **k: sp.Integer(56))
    r = S("k", "1", "10")
    assert r["error"]["code"] == "VERIFICATION_FAILED" and r.get("exact_result") is None


# ---------------- sustitución
def test_sustitucion():
    assert ok(call(operation="substitute", expression="x^2+y", params={"values": {"x": "2", "y": "a+1"}}))["exact_result"] == "a + 5"


def test_sustitucion_sin_valores():
    assert call(operation="substitute", expression="x+1", params={})["status"] == "invalid_input"


# ---------------- matrices simbólicas
def M(op, a, **kw):
    return call(operation="matrix_symbolic", structured_input={"a": a, **kw}, params={"op": op})


def test_determinante_simbolico():
    assert ok(M("det", [["a", "b"], ["c", "d"]]))["exact_result"] == "a*d - b*c"


def test_inversa_simbolica_con_condicion():
    r = ok(M("inverse", [["a", "b"], ["c", "d"]]))
    assert "a*d - b*c ≠ 0" in r["conditions"] and r["data"]["matrix"][0][0] == "d/(a*d - b*c)"


def test_inversa_singular():
    assert M("inverse", [["1", "2"], ["2", "4"]])["status"] == "domain_error"


def test_autovalores_simbolicos():
    vals = {e["value"] for e in ok(M("eigen", [["a", "1"], ["1", "a"]]))["data"]["eigenvalues"]}
    assert vals == {"a - 1", "a + 1"}


def test_producto_simbolico():
    r = ok(M("mul", [["a", "0"], ["0", "1"]], b=[["1", "b"], ["0", "1"]]))
    assert r["data"]["matrix"] == [["a", "a*b"], ["0", "1"]]


# ---------------- lógica
def test_morgan():
    assert ok(call(operation="logic", expression="~(p & q)"))["exact_result"] == "¬p ∨ ¬q"


def test_tautologia_y_contradiccion():
    assert ok(call(operation="logic", expression="p | ~p"))["data"]["classification"] == "tautología"
    assert ok(call(operation="logic", expression="p y no p"))["data"]["classification"] == "contradicción"


def test_modus_ponens_y_tabla():
    r = ok(call(operation="logic", expression="(p → q) ∧ p"))
    assert r["exact_result"] == "p ∧ q" and len(r["data"]["truth_table"]) == 4


def test_logica_saboteada(monkeypatch):
    import sympy.logic.boolalg as B
    monkeypatch.setattr(B, "simplify_logic", lambda e, *a, **k: e.args[0] if e.args else e)
    assert call(operation="logic", expression="p & q")["error"]["code"] == "VERIFICATION_FAILED"


# ---------------- conjuntos
@pytest.mark.parametrize("expr, res", [
    ("[0,2] ∪ [1,3]", "[0, 3]"), ("{1,2,3} ∩ {2,3,4}", "{2, 3}"), ("[0,5] \\ {2}", "[0, 2) ∪ (2, 5]"),
    ("(0,1) ∩ [2,3]", "∅ (sin solución)"),
])
def test_conjuntos(expr, res):
    assert ok(call(operation="sets", expression=expr))["exact_result"] == res


# ---------------- derivación implícita
def test_derivada_implicita_circunferencia():
    r = ok(call(operation="implicit_diff", expression="x^2+y^2=1"))
    assert r["exact_result"] == "-x/y" and "2*y ≠ 0" in r["conditions"]


def test_capacidades_07():
    import json
    import os
    c = call(operation="capabilities")["data"]
    assert c["engine_version"] == "0.7.0" and c["api_version"] == "1.3" and "logica_proposicional" in c["modules"]
    ruta = os.path.join(os.path.dirname(__file__), "..", "schema", "request.schema.json")
    with open(ruta, encoding="utf-8") as f:
        ops = set(json.load(f)["properties"]["operation"]["enum"])
    assert set(advanced2.ADVANCED2_OPS) <= ops
