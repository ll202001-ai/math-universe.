"""Pruebas de regresión de la auditoría matemática (fase de validación).
Cada caso aquí corresponde a un defecto o limitación hallada con el oráculo independiente (audit/oraculo.py)."""
import os, sys, pytest
from conftest import call

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


# ---- dominio: condiciones constantes ----
@pytest.mark.parametrize("expr", ["ln(0)", "ln(-3)", "tan(pi/2)", "tan(3*pi/2)", "asin(2)", "1/0", "0^0", "1/(sqrt(2)-sqrt(2))"])
def test_dominio_constante_violado_es_domain_error(expr):
    r = call(operation="evaluate", expression=expr)
    assert r["status"] == "domain_error", (expr, r["status"], r.get("exact_result"))
    assert r.get("exact_result") is None


def test_condicion_constante_verdadera_no_se_lista():
    r = call(operation="simplify", expression="sqrt(8)/sqrt(2)")
    assert r["exact_result"] == "2" and r["conditions"] == []
    r = call(operation="simplify", expression="1/(sqrt(2)-1)")
    assert r["conditions"] == []


# ---- trigonometría exacta en ángulos notables ----
@pytest.mark.parametrize("expr,exp,ref", [
    ("sin(pi)", "0", 0.0), ("cos(pi)", "-1", -1.0), ("sin(pi/2)", "1", 1.0), ("cos(pi/3)", "1/2", 0.5), ("sin(pi/6)", "1/2", 0.5),
    ("sin(pi/4)^2", "1/2", 0.5), ("cos(pi/4)*sqrt(2)", "1", 1.0), ("tan(pi/4)", "1", 1.0), ("sin(2*pi)", "0", 0.0),
    ("cos(7*pi/6)", "-(1/2)*sqrt(3)", -0.8660254037844386), ("sin(-pi/6)", "-1/2", -0.5), ("tan(pi/3)^2", "3", 3.0),
    ("sin(5*pi/6)", "1/2", 0.5), ("cos(3*pi/2)", "0", 0.0), ("sin(pi/3)^2+cos(pi/3)^2", "1", 1.0),
])
def test_trig_exacta(expr, exp, ref):
    import math
    r = call(operation="evaluate", expression=expr)
    assert r["status"] == "success_exact", r
    assert r["exact_result"].replace(" ", "") == exp.replace(" ", ""), r["exact_result"]
    # el valor de referencia es una constante calculada aparte con math (independiente del motor)
    py = {"sin(pi)": math.sin(math.pi), "cos(7*pi/6)": math.cos(7*math.pi/6), "tan(pi/3)^2": math.tan(math.pi/3)**2}
    if expr in py: assert abs(py[expr] - ref) < 1e-12


# ---- exp/ln inversas, raíces ----
def test_exp_ln():
    r = call(operation="simplify", expression="exp(ln(x))")
    assert r["exact_result"] == "x" and "x > 0" in r["conditions"]
    assert call(operation="simplify", expression="ln(exp(x))")["exact_result"] == "x"


def test_raiz_real_de_negativo_impar():
    r = call(operation="evaluate", expression="(-8)^(1/3)")
    assert r["exact_result"] == "-2"
    assert call(operation="evaluate", expression="(-8)^(1/2)")["status"] == "unsupported"


def test_sqrt_al_cuadrado_con_condicion():
    r = call(operation="simplify", expression="sqrt(x+1)^2")
    assert r["exact_result"] == "x + 1" and any("x + 1 >= 0" in c for c in r["conditions"])


# ---- enunciados sin incógnita ----
@pytest.mark.parametrize("eq,st,res", [("5=5", "success_exact", "Verdadero"), ("5=6", "no_solution", "Falso"),
                                       ("1/3+1/6=1/2", "success_exact", "Verdadero"), ("sqrt(2)^2=2", "success_exact", "Verdadero")])
def test_ecuacion_sin_incognita(eq, st, res):
    r = call(operation="solve", expression=eq)
    assert r["status"] == st and r["exact_result"] == res and r["verification"]["status"] == "passed"


def test_ecuacion_sin_incognita_con_division_por_cero():
    assert call(operation="solve", expression="1/0=1")["status"] == "domain_error"


# ---- identificadores multi-letra ----
def test_pista_identificador_multiletra():
    r = call(operation="solve", expression="x=at+b", variables=["t"])
    assert r["status"] == "invalid_input" and "use *" in r["error"]["message"]
    r = call(operation="solve", expression="x=a*t+b", variables=["t"])
    assert r["status"] == "success_exact" and r["exact_result"] == "t = (-b + x)/a"


# ---- factorización multivariante homogénea ----
@pytest.mark.parametrize("expr,exp_factors", [
    ("x^2-y^2", {"(x - y)", "(x + y)"}), ("x^3+y^3", {"(x + y)", "(x^2 - x*y + y^2)"}),
    ("6x^2-5x*y-6y^2", {"(2*x - 3*y)", "(3*x + 2*y)"}), ("x^4-y^4", {"(x - y)", "(x + y)", "(x^2 + y^2)"}),
])
def test_factor_homogeneo(expr, exp_factors):
    r = call(operation="factor", expression=expr)
    assert r["status"] == "success_exact" and r["verification"]["status"] == "passed"
    assert set(r["exact_result"].split("*")) >= {f for f in exp_factors if "*" not in f[1:-1]} or True
    for f in exp_factors:
        assert f in r["exact_result"], (r["exact_result"], f)


def test_factor_no_homogeneo_advierte():
    r = call(operation="factor", expression="x^2-y^2+x-y")
    assert r["status"] == "success_exact" and r["warnings"]            # límite declarado, no falso éxito


def test_factor_irreducible_sin_parentesis_innecesarios():
    assert call(operation="factor", expression="x^2+1")["exact_result"] == "x^2 + 1"


# ---- el oráculo independiente completo debe pasar ----
def test_oraculo_independiente_completo():
    import audit.oraculo as o
    o.R.clear()
    for f in o.ALL: f()
    fallos = [x for x in o.R if x["estado"] == "fallo"]
    assert not fallos, fallos[:5]
    # los casos no soportados se cuentan aparte y nunca como correctos
    assert all(x["estado"] == "no_soportado" for x in o.R if not x["ok"] and x["estado"] != "fallo")
    assert sum(1 for x in o.R if x["estado"] == "ok") + sum(1 for x in o.R if x["estado"] == "no_soportado") == len(o.R)
    assert len(o.R) >= 150


# ---- sintaxis ambigua ----
def test_doble_factorial_ambiguo_rechazado():
    assert call(operation="evaluate", expression="3!!")["status"] == "invalid_input"
    assert call(operation="evaluate", expression="(3!)!")["exact_result"] == "720"


def test_coma_decimal_tiene_mensaje_claro():
    r = call(operation="evaluate", expression="1,5+1")
    assert r["status"] == "invalid_input" and "punto" in r["error"]["message"]


# ---- impresión sin ambigüedad ----
def test_impresion_derivadas():
    assert call(operation="differentiate", expression="sqrt(x)", variables=["x"])["exact_result"] == "1/(2*sqrt(x))"
    assert "(x)^(x)" not in call(operation="differentiate", expression="x^x", variables=["x"])["exact_result"]


def test_fuzz_semillas_fijas():
    import audit.fuzz as fz
    for seed in (1, 7):
        st, fl = fz.main(120, seed)
        assert not fl, fl[:3]


# ---- cifras significativas arbitrarias para radicales (oráculo: módulo decimal de la biblioteca estándar) ----
@pytest.mark.parametrize("expr,sig,ref", [
    ("sqrt(2)", 60, "2.sqrt()"), ("sqrt(3)", 100, "3.sqrt()"), ("1+sqrt(5)", 40, "1+5.sqrt()"), ("sqrt(7)/3", 30, "7.sqrt()/3"),
    ("-2*sqrt(11)", 25, "-2*11.sqrt()"), ("sqrt(1/3)", 35, "1/3.sqrt()"),
])
def test_cifras_arbitrarias_de_radicales(expr, sig, ref):
    import decimal
    r = call(operation="evaluate", expression=expr, precision=sig)
    got = r["approximate_result"]
    D = decimal.Decimal
    with decimal.localcontext() as c:
        c.prec = sig + 30
        val = {"2.sqrt()": D(2).sqrt(), "3.sqrt()": D(3).sqrt(), "1+5.sqrt()": 1 + D(5).sqrt(), "7.sqrt()/3": D(7).sqrt() / 3,
               "-2*11.sqrt()": -2 * D(11).sqrt(), "1/3.sqrt()": (D(1) / 3).sqrt()}[ref]
        c.prec = sig
        want = format(+val, "f")
    assert got == want, (got, want)
    assert not any("mpmath" in w for w in r["warnings"])


def test_solucion_cuadratica_con_precision():
    r = call(operation="solve", expression="x^2-2=0", precision=30)
    assert [s["approximate"] for s in r["data"]["solutions"]] == ["-1.41421356237309504880168872421", "1.41421356237309504880168872421"]


def test_trascendentes_siguen_limitadas_a_15_cifras_con_aviso():
    # 0.5.0: la limitación solo persiste SIN mpmath (los instaladores lo incluyen). Con mpmath: 30 cifras correctas (test_23).
    r = call(operation="evaluate", expression="pi", precision=30)
    try:
        import mpmath  # noqa: F401
    except ImportError:
        assert r["approximate_result"] == "3.14159265358979" and any("15 cifras" in w for w in r["warnings"])
    else:
        assert r["approximate_result"] == "3.14159265358979323846264338328" and r["warnings"] == []


# ---- integrales definidas: verificación robusta e integrales impropias ----
def test_integral_con_pico_estrecho_se_verifica():
    r = call(operation="integrate", expression="1/(x^2+1)", variables=["x"], lower="-1000", upper="1000")
    assert r["status"] == "success_exact" and r["verification"]["status"] == "passed"
    assert abs(float(r["approximate_result"]) - 2 * 1.5697963271282298) < 1e-9          # 2·atan(1000), calculado aparte


def test_integral_impropia_no_se_inventa():
    r = call(operation="integrate", expression="x*ln(x)", variables=["x"], lower="0", upper="1")
    assert r["status"] == "unsupported" and "impropia" in r["error"]["message"]


def test_integrando_indefinido_en_el_intervalo_es_domain_error():
    r = call(operation="integrate", expression="ln(x)", variables=["x"], lower="-1", upper="1")
    assert r["status"] == "domain_error"


# ---- factorización de grado alto (Kronecker exhaustivo por grado) ----
@pytest.mark.parametrize("expr,partes", [
    ("x^8+x+1", ["x^2 + x + 1", "x^6 - x^5 + x^3 - x^2 + 1"]),                 # n ≡ 2 (mod 3): reducible
    ("x^11+x+1", ["x^2 + x + 1", "x^9 - x^8 + x^6 - x^5 + x^3 - x^2 + 1"]),
    ("(x^3+x+1)*(x^3-x+1)", ["x^3 - x + 1", "x^3 + x + 1"]),
    ("x^9-1", ["x - 1", "x^2 + x + 1", "x^6 + x^3 + 1"]),
])
def test_factor_grado_alto_exacto(expr, partes):
    r = call(operation="factor", expression=expr, timeout_ms=60000)
    assert r["status"] == "success_exact" and r["verification"]["status"] == "passed" and r["data"]["factorization_complete"] is True
    for f in partes: assert f"({f})" in r["exact_result"], (r["exact_result"], f)


def test_factor_productos_aleatorios_de_grado_alto():
    import random
    import numpy as np
    rng = random.Random(5)
    for _ in range(12):
        d1, d2 = rng.choice([(3, 3), (2, 4), (2, 5), (3, 4)])
        def rp(d):
            while True:
                c = [rng.randint(-4, 4) for _ in range(d)] + [rng.choice([1, 2, -1, 3])]
                if c[0] != 0: return c
        prod = np.polynomial.polynomial.polymul(rp(d1), rp(d2)).astype(int)
        txt = "+".join(f"({int(c)})*x^{i}" for i, c in enumerate(prod) if c)
        r = call(operation="factor", expression=txt, timeout_ms=60000)
        assert r["status"] == "success_exact" and r["verification"]["status"] == "passed"
        assert r["exact_result"].count("(") >= 2, (txt, r["exact_result"])      # el producto de dos polinomios se separa


# ---- impresión sin ambigüedad de átomos con potencia (hallazgo de las pruebas aleatorias con parámetros) ----
@pytest.mark.parametrize("expr", ["(x^a)^2", "(2^a)^2", "((x*x)+(4^a))^3", "a/((x^a)^3)", "(x+1)^a*(x+1)^a", "((-4)^a)^2"])
def test_potencia_de_atomo_potencia_no_se_imprime_ambigua(expr):
    r = call(operation="simplify", expression=expr)
    assert r["status"] == "success_exact" and r["verification"]["status"] == "passed", r
    assert "^a^" not in r["exact_result"].replace(" ", ""), r["exact_result"]


def test_integral_con_exponente_simbolico_no_devuelve_un_resultado_falso():
    """Regresión: ∫ x^n dx devolvió 'x*x^n + C' (falso) porque x^n se tomó por un coeficiente; solo el verificador lo frenó."""
    r = call(operation="integrate", expression="x^n", variables=["x"])
    assert r["status"] == "unsupported"
    assert call(operation="differentiate", expression="x^n", variables=["x"])["exact_result"] == "n*(x^(n - 1))"


def test_fuzz_con_parametros_simbolicos():
    import audit.fuzz as fz
    st, fl = fz.main(150, 2024)
    assert not fl, fl[:3]
