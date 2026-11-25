"""Pruebas que REQUIEREN SymPy. En un entorno sin SymPy se OMITEN (y el informe las cuenta como omitidas,
nunca como aprobadas). Ejecutar con: pip install sympy mpmath  y luego pytest tests/test_08_sympy.py -v"""
import pytest
sympy = pytest.importorskip("sympy", reason="SymPy no está instalado en este entorno")
from conftest import call


@pytest.fixture(autouse=True)
def _habilitar_sympy(monkeypatch):
    monkeypatch.delenv("MATH_UNIVERSE_DISABLE_SYMPY", raising=False)     # en este módulo el respaldo SymPy SÍ está activo
from math_universe_engine import symbolic
from math_universe_engine.ast_tools import normalize
from math_universe_engine.parser import parse
from math_universe_engine.verify import equivalent


def A(s): return normalize(parse(s))


def test_sympy_disponible():
    assert symbolic.available()


# Hallazgo de Windows nº1 y nº2 (ver docs/HALLAZGOS_WINDOWS_1.md): SymPy imprime «3*x**2»; symbolic.run() traduce a la sintaxis del
# motor («3*x^2») a propósito, para que el resultado se pueda volver a analizar. La diferencia es SOLO de representación. Se prueba
# (a) el contrato de representación y (b) la equivalencia matemática contra SymPy puro, sin comparar cadenas entre sí.
@pytest.mark.parametrize("op,expr,crudo_sympy,esperado_motor", [("differentiate", "x^3", "3*x**2", "3*x^2"),
                                                                 ("expand", "(x+1)^2", "x**2 + 2*x + 1", "x^2 + 2*x + 1")])
def test_backend_sympy_representacion_y_equivalencia(op, expr, crudo_sympy, esperado_motor):
    x = sympy.Symbol("x")
    base = sympy.sympify(expr.replace("^", "**"))
    ref = sympy.diff(base, x) if op == "differentiate" else sympy.expand(base)
    assert str(ref) == crudo_sympy                               # el crudo de SymPy es el que se observó en Windows
    res = symbolic.run(op, A(expr), ["x"])
    assert res == esperado_motor and "**" not in res             # contrato de representación del motor
    assert sympy.simplify(sympy.sympify(res.replace("^", "**")) - ref) == 0      # equivalencia algebraica (SymPy puro)
    if op == "expand": assert equivalent(A(expr), res) == "passed"        # (para derivar, la equivalencia ya se comprobó contra SymPy puro)


def test_backend_sympy_factor():
    res = symbolic.run("factor", A("x^2-9"), ["x"])
    assert equivalent(A("x^2-9"), res) == "passed"


def test_pdf_fase0_x2_menos_1_sobre_x_menos_1_con_sympy():
    res = symbolic.run("simplify", A("(x^2-1)/(x-1)"), None)
    assert res == "x + 1"


@pytest.mark.parametrize("expr", ["sin(x)^2", "x*atan(x)", "sqrt(x)"])
def test_respaldo_integral_cuando_el_motor_propio_no_puede(expr):
    r = call(operation="integrate", expression=expr)
    assert r["status"] in ("success_exact", "unsupported")
    if r["status"] == "success_exact":
        assert r["method"] == "sympy_respaldo_experimental"
        assert r["verification"]["status"] in ("passed", "not_possible")


# Hallazgo de Windows nº3: 1/(x^3+1) lo resuelve el integrador PROPIO (fracciones parciales con cuadrático irreducible), por lo que el
# respaldo NO debe activarse. La expectativa antigua suponía que el motor propio no podía; era la prueba la que estaba desactualizada.
def test_integral_que_el_motor_propio_resuelve_no_usa_el_respaldo(monkeypatch):
    def _no_debe_llamarse(*a, **k): raise AssertionError("se invocó el respaldo SymPy aunque el motor propio podía")
    monkeypatch.setattr(symbolic, "run", _no_debe_llamarse)
    r = call(operation="integrate", expression="1/(x^3+1)")
    assert r["status"] == "success_exact" and r["method"] == "integracion_simbolica_propia"
    assert r["verification"]["status"] == "passed"


def test_integral_propia_de_1_sobre_x3_mas_1_coincide_con_sympy():
    """Hallazgo de Windows nº4 (docs/HALLAZGOS_WINDOWS_2.md). La primitiva contiene ln|x+1|, cuya derivada solo tiene sentido en los REALES.
    Con x complejo (Symbol por defecto) SymPy deriva Abs() mediante re/im/Piecewise y no puede simplificar: fallo de HIPÓTESIS del
    comparador, no de la primitiva. Aquí x es real y la comparación se hace por ramas del valor absoluto (x ≠ -1)."""
    x = sympy.Symbol("x", real=True)
    integrando = 1 / (x**3 + 1)
    r = call(operation="integrate", expression="1/(x^3+1)")
    assert r["status"] == "success_exact" and "x ≠ -1" in r["conditions"]
    own = sympy.sympify(from_engine(r["exact_result"].replace(" + C", "")),
                        locals={"x": x, "ln": sympy.log, "atan": sympy.atan, "sqrt": sympy.sqrt, "abs": sympy.Abs})
    # (a) demostración simbólica por ramas: en x>-1, |x+1| = x+1; en x<-1, |x+1| = -(x+1)
    for signo, rama in ((1, "x > -1"), (-1, "x < -1")):
        sin_abs = own.replace(sympy.Abs, lambda a, s=signo: s * a)
        assert sympy.simplify(sympy.diff(sin_abs, x) - integrando) == 0, rama
    # (b) comprobación numérica independiente de la derivada (sin simplify) en ambos intervalos, alta precisión
    d = sympy.diff(own, x)
    for v in (-100, -7, -2, -1.5, -1.001, -0.999, -0.5, 0, 0.3, 1, 4, 100):
        got = d.subs(x, sympy.Rational(v)).evalf(30)
        assert abs(got - integrando.subs(x, sympy.Rational(v)).evalf(30)) < sympy.Float("1e-20"), v
    # (c) misma primitiva que SymPy salvo constante (en x > -1, donde log(x+1) es real)
    ref = sympy.integrate(integrando, x)
    difs = [(own - ref).subs(x, sympy.Rational(v)).evalf(30) for v in (-0.5, 0, 1, 3, 10)]
    assert all(abs(sympy.im(dd)) < sympy.Float("1e-20") for dd in difs), difs
    assert max(sympy.re(dd) for dd in difs) - min(sympy.re(dd) for dd in difs) < sympy.Float("1e-20"), difs


def from_engine(t):
    return t.replace("^", "**")


# Pruebas diferenciales: motor propio vs SymPy en un corpus común
@pytest.mark.parametrize("expr", ["x^3*sin(x)", "(x^2+1)/(x-1)", "exp(2*x)*x", "ln(x)/x", "x^x"])
def test_diferencial_derivadas(expr):
    own = call(operation="differentiate", expression=expr)
    x = sympy.Symbol("x")
    from sympy.parsing.sympy_parser import parse_expr, standard_transformations, convert_xor
    ref = sympy.diff(parse_expr(expr, transformations=standard_transformations + (convert_xor,)), x)
    assert equivalent(A(str(ref).replace("**", "^")), own["exact_result"]) in ("passed",)


@pytest.mark.parametrize("eq", ["x^2-5x+6", "x^3-6x^2+11x-6", "2x^2-3x-2", "x^4-5x^2+4"])
def test_diferencial_raices(eq):
    from sympy.parsing.sympy_parser import parse_expr, standard_transformations, implicit_multiplication_application, convert_xor
    tr = standard_transformations + (implicit_multiplication_application, convert_xor)
    own = call(operation="solve", expression=eq + "=0")
    x = sympy.Symbol("x")
    ref = sorted(sympy.solve(parse_expr(eq, transformations=tr), x))
    vals = sorted(float(s["approximate"]) for s in own["data"]["solutions"])
    assert vals == pytest.approx([float(r) for r in ref])


# ---- comparación diferencial completa (corpus de audit/comparar_sympy.py) ----
def test_comparacion_motor_vs_sympy_corpus_completo(tmp_path):
    import audit.comparar_sympy as c
    ad = c.SympyAdapter()
    cnt, filas = c.ejecutar(ad, str(tmp_path / "comparacion.json"))
    hallazgos = [f for f in filas if f["veredicto"] in c.HALLAZGOS]
    # Cualquier diferencia, discrepancia de dominio, caso no concluyente o fallo del comparador es un HALLAZGO que hay que analizar:
    # no se toleran ni se convierten en advertencias. Solo la convención documentada (c.CONVENCIONES) se acepta, y solo si coincide exactamente.
    assert not hallazgos, [(f["veredicto"], f["op"], f["expr"], f["detalle"][:160]) for f in hallazgos[:10]]
    # la cobertura cruzada debe ser real: la mayoría de los casos tiene que tener referencia de SymPy
    con_ref = len(filas) - cnt.get("SIN_REFERENCIA_SYMPY", 0) - cnt.get("AMBOS_NO_SOPORTAN", 0)
    assert con_ref >= 0.6 * len(filas), cnt


# ---- Ronda 4: los dos hallazgos pendientes de la fase 7, con SymPy real (solo se pueden ejecutar donde SymPy está instalado) ----
def test_comparador_demuestra_por_ramas_la_derivada_de_la_primitiva():
    """equals() es heurístico; la demostración por ramas es exacta (cancel=0 en cada intervalo). Negativos incluidos: no 'demuestra' lo falso."""
    import audit.comparar_sympy as c
    ad = c.SympyAdapter()
    r = call(operation="integrate", expression="1/(x^3+1)")
    mot = ad.parse(r["exact_result"].replace(" + C", "").strip())
    integrando = ad.parse("1/(x^3+1)")
    assert ad.igual_simbolico_por_ramas(ad.derivada(mot), integrando) is True
    assert ad.igual_simbolico_por_ramas(ad.derivada(ad.parse("ln(abs(x+1))/3")), integrando) is not True          # primitiva incompleta
    assert ad.igual_simbolico_por_ramas(ad.derivada(ad.parse("ln(abs(x+1))/3 + atan(x)")), integrando) is not True
    assert ad.igual_simbolico_por_ramas(ad.parse("x/abs(x)"), ad.sp.sign(ad.x)) is True
    assert ad.igual_simbolico_por_ramas(ad.parse("x/abs(x)"), ad.parse("1")) is not True                   # x/|x| no es 1


def test_comparador_registra_ambos_resultados_de_equals_y_demostracion():
    import audit.comparar_sympy as c
    ad = c.SympyAdapter()
    case = {"op": "integrate", "expr": "1/(x^3+1)", "id": 0}
    v, det = c.clasificar(case, c._motor(case), ad.reference(case), ad)
    assert v in ("IDENTICO", "EQUIVALENTE"), (v, det)


def test_singularidad_evitable_x3_menos_8_sobre_x_menos_2_con_sympy_real():
    import audit.comparar_sympy as c
    from fractions import Fraction
    ad = c.SympyAdapter()
    assert ad.indefinida_en("(x^3-8)/(x-2)", Fraction(2)) is True        # sin autosimplificar: indefinida en 2
    assert ad.indefinida_en("x/x", Fraction(0)) is True
    assert ad.indefinida_en("x^2+2*x+4", Fraction(2)) is False
    assert ad.limite_en("(x^3-8)/(x-2)", Fraction(2)) == "12"          # singularidad EVITABLE: el límite existe y vale 12
    case = {"op": "simplify", "expr": "(x^3-8)/(x-2)", "id": 0}
    m = c._motor(case)
    assert "x ≠ 2" in m["conditions"]
    v, det = c.clasificar(case, m, ad.reference(case), ad)
    assert v in ("EQUIVALENTE", "IDENTICO", "SYMPY_AMPLIA_DOMINIO"), (v, det)


def test_mpmath_disponible_para_precision_arbitraria():
    mpmath = pytest.importorskip("mpmath")
    mpmath.mp.dps = 50
    assert str(mpmath.sqrt(2))[:30] == "1.4142135623730950488016887242"
