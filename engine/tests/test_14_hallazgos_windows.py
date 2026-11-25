"""Regresiones de los hallazgos de la primera validación en Windows (docs/HALLAZGOS_WINDOWS_1.md). No requieren SymPy."""
import math
import pytest
from scipy.integrate import quad
from conftest import call
from math_universe_engine import symbolic


@pytest.mark.parametrize("crudo,motor", [("3*x**2", "3*x^2"), ("x**2 + 2*x + 1", "x^2 + 2*x + 1"), ("Abs(x)", "abs(x)"),
                                         ("log(x)/E", "ln(x)/e"), ("x**(x**2)", "x^(x^2)"), ("I*x", "i*x")])
def test_traduccion_de_sintaxis_de_sympy(crudo, motor):
    assert symbolic.from_sympy_text(crudo) == motor


def test_traduccion_no_toca_identificadores_con_E_o_I():
    assert symbolic.from_sympy_text("Exp1 + Index") == "Exp1 + Index"


def test_integral_propia_1_sobre_x3_mas_1_es_correcta_con_oraculo_independiente():
    """Primitiva clásica escrita a mano (no del motor): ∫0^b 1/(x³+1) dx. Se compara la primitiva del motor, evaluada por
    el verificador del motor en forma definida, con scipy.quad."""
    r = call(operation="integrate", expression="1/(x^3+1)")
    assert r["status"] == "success_exact" and r["method"] == "integracion_simbolica_propia"
    assert r["verification"]["status"] == "passed"
    rd = call(operation="integrate", expression="1/(x^3+1)", lower="0", upper="2")
    ref, _ = quad(lambda t: 1 / (t**3 + 1), 0, 2)
    assert rd["status"] == "success_exact"
    assert abs(float(rd["approximate_result"]) - ref) < 1e-9


def test_el_respaldo_no_se_usa_si_el_motor_propio_puede(monkeypatch):
    monkeypatch.setenv("MATH_UNIVERSE_DISABLE_SYMPY", "0")
    monkeypatch.setattr(symbolic, "available", lambda: True)
    def boom(*a, **k): raise AssertionError("respaldo invocado")
    monkeypatch.setattr(symbolic, "run", boom)
    r = call(operation="integrate", expression="1/(x^3+1)")
    assert r["method"] == "integracion_simbolica_propia"


# ---- Hallazgo de Windows nº4: ∫1/(x^3+1) ----
def _F(txt):
    t = txt.replace(" + C", "").replace("^", "**")
    return lambda x: eval(t, {"__builtins__": {}}, {"x": x, "ln": math.log, "abs": abs, "atan": math.atan, "sqrt": math.sqrt})


@pytest.mark.parametrize("x", [-100.0, -50.0, -5.0, -2.0, -1.5, -0.5, 0.0, 0.3, 1.0, 4.0, 100.0])
def test_derivada_de_la_primitiva_coincide_a_ambos_lados_de_la_singularidad(x):
    """Oráculo sin SymPy: derivada numérica (centrales) de la primitiva del motor vs 1/(x³+1), en (-∞,-1) y (-1,∞)."""
    r = call(operation="integrate", expression="1/(x^3+1)")
    F, h = _F(r["exact_result"]), 1e-6
    d = (F(x + h) - F(x - h)) / (2 * h)
    assert abs(d - 1 / (x**3 + 1)) < 1e-8 * (1 + abs(1 / (x**3 + 1)))  + 1e-9


@pytest.mark.parametrize("expr,cond", [("1/(x^3+1)", "x ≠ -1"), ("1/x", "x ≠ 0"), ("1/(x-2)", "x ≠ 2"), ("ln(x)", "x > 0"), ("x*ln(x)", "x > 0")])
def test_integral_indefinida_informa_el_dominio_del_integrando(expr, cond):
    """Defecto real hallado junto con el nº4: antes la primitiva se entregaba sin ninguna condición de dominio."""
    r = call(operation="integrate", expression=expr)
    assert r["status"] == "success_exact" and cond in r["conditions"], r["conditions"]


@pytest.mark.parametrize("expr", ["x^2", "sin(x)", "exp(x)"])
def test_integral_sin_restricciones_no_inventa_condiciones(expr):
    assert call(operation="integrate", expression=expr)["conditions"] == []


# ---- Hallazgos de Windows nº3 (docs/HALLAZGOS_WINDOWS_3.md): oráculo independiente del motor y de SymPy ----
@pytest.mark.parametrize("x", [-50.0, -3.0, -0.5, -1e-3, 1e-3, 0.5, 3.0, 50.0])
def test_derivada_de_abs_es_x_sobre_abs_x_fuera_de_cero(x):
    r = call(operation="differentiate", expression="abs(x)", variables=["x"])
    assert r["status"] == "success_exact" and r["exact_result"] == "x/abs(x)"
    h = 1e-6 * max(1.0, abs(x)) if abs(x) > 1e-2 else 1e-6
    num = (abs(x + h) - abs(x - h)) / (2 * h)
    assert abs(num - x / abs(x)) < 1e-6
    assert num == pytest.approx(math.copysign(1.0, x), abs=1e-6)             # = sign(x), como dice SymPy, fuera de 0


def test_abs_no_es_derivable_en_cero_y_el_motor_lo_excluye():
    """En x=0 los cocientes laterales de |x| valen -1 y +1: la derivada NO existe. SymPy fija sign(0)=0 (convención de la función
    signo); el motor, que dice x ≠ 0, es el matemáticamente correcto. Representación normalizada: 'x ≠ 0', no 'abs(x) ≠ 0'."""
    for h in (1e-3, 1e-6, 1e-9):
        assert (abs(0 + h) - abs(0)) / h == 1.0 and (abs(0) - abs(0 - h)) / h == -1.0
    r = call(operation="differentiate", expression="abs(x)", variables=["x"])
    assert r["conditions"] == ["x ≠ 0"], r["conditions"]


def test_x_sobre_x_es_uno_solo_donde_x_no_es_cero():
    """x/x vale 1 salvo en x=0 (indefinida). SymPy lo reduce a 1 al construirlo y pierde la restricción; el motor la conserva."""
    with pytest.raises(ZeroDivisionError):
        (lambda x: x / x)(0.0)                                              # la función original no existe en 0
    r = call(operation="simplify", expression="x/x")
    assert r["exact_result"] == "1" and r["conditions"] == ["x ≠ 0"] and r["verification"]["status"] == "passed"
    for e in ("(x^2)/x", "(x+1)/(x+1)", "(x^2-4)/(x-2)"):
        assert call(operation="simplify", expression=e)["conditions"], e


def test_ecuacion_constante_convencion_documentada_proposicion_frente_a_conjunto():
    t = call(operation="solve", expression="5=5")
    f = call(operation="solve", expression="5=6")
    ident = call(operation="solve", expression="x=x")
    assert (t["status"], t["exact_result"]) == ("success_exact", "Verdadero")
    assert f["status"] == "no_solution"
    assert ident["status"] == "multiple_solutions"                          # con incógnita sí es un conjunto solución (todo el dominio)


@pytest.mark.parametrize("cond_in,cond_out", [("abs(x) ≠ 0", "x ≠ 0"), ("abs(x + 1) ≠ 0", "x + 1 ≠ 0"), ("abs(x) + 1 ≠ 0", "abs(x) + 1 ≠ 0"),
                                              ("abs(x)*abs(y) ≠ 0", "abs(x)*abs(y) ≠ 0"), ("x ≠ 0", "x ≠ 0")])
def test_normalizacion_de_condiciones_abs(cond_in, cond_out):
    from math_universe_engine.dispatcher import _norm_cond
    assert _norm_cond(cond_in) == cond_out


# ======= Ronda 4: hallazgos pendientes del informe de la fase 7 =======
from fractions import Fraction


def _eval_exacto(txt, x):
    """Evalúa el texto del motor con Fractions EXACTAS (sin coma flotante); solo + - * / ^ enteros."""
    return eval(txt.replace("^", "**"), {"__builtins__": {}}, {"x": x})


@pytest.mark.parametrize("n", [2, 3, 4, 5, 6])
@pytest.mark.parametrize("a", [-3, -1, 2, 5])
@pytest.mark.parametrize("op", ["simplify", "expand", "factor"])
def test_la_cancelacion_conserva_la_condicion_x_distinto_de_a(n, a, op):
    """(x^n - a^n)/(x - a): tras cancelar, el motor DEBE conservar x ≠ a. No basta la equivalencia algebraica:
    (1) la función original no existe en x=a (ZeroDivisionError con Fractions exactas); (2) el resultado SÍ existe en a (sería falso extenderlo
    sin avisar); (3) igualdad EXACTA con el original en 12 racionales; (4) la condición está en `conditions`."""
    expr = f"(x^{n}-({a})^{n})/(x-({a}))"
    with pytest.raises(ZeroDivisionError):
        _eval_exacto(expr, Fraction(a))
    r = call(operation=op, expression=expr)
    assert r["status"] == "success_exact", r
    assert f"x ≠ {a}" in r["conditions"], (expr, op, r["conditions"], r["exact_result"])
    for p in [Fraction(k, 7) for k in range(-40, 40, 7) if Fraction(k, 7) != a] + [Fraction(a) + Fraction(1, 1000)]:
        assert _eval_exacto(r["exact_result"], p) == _eval_exacto(expr, p), (expr, op, r["exact_result"], p)
    if op in ("simplify", "factor"):
        _eval_exacto(r["exact_result"], Fraction(a))                       # el resultado simplificado sí está definido en a: por eso la condición es imprescindible


def test_x3_menos_8_sobre_x_menos_2_casos_pedidos_en_el_informe():
    r = call(operation="simplify", expression="(x^3-8)/(x-2)")
    assert r["exact_result"] == "x^2 + 2*x + 4" and r["conditions"] == ["x ≠ 2"]
    # combinaciones: la condición sobrevive a sumas, potencias, productos y a que otra parte del resultado quede sin singularidad
    for e, extra in [("(x^3-8)/(x-2)+1", []), ("((x^3-8)/(x-2))^2", []), ("(x^3-8)/(x-2)-(x^2+2*x+4)", []),
                     ("x*(x^3-8)/(x-2)", []), ("(x^3-8)/((x-2)*(x+1))", ["x ≠ -1"])]:
        rr = call(operation="simplify", expression=e)
        assert "x ≠ 2" in rr["conditions"] and all(c in rr["conditions"] for c in extra), (e, rr["conditions"])


def test_expand_de_cero_sobre_algo_se_imprime_cero():
    """Hallazgo menor de esta ronda: expand((x^3-8)/(x-2)-(x^2+2x+4)) devolvía '0/(x - 2)'."""
    r = call(operation="expand", expression="(x^3-8)/(x-2)-(x^2+2*x+4)")
    assert r["exact_result"] == "0" and r["conditions"] == ["x ≠ 2"]


# --- ∫ 1/(x^3+1): demostración exacta con aritmética racional (sin SymPy, sin coma flotante) ---
def test_derivada_de_la_primitiva_clasica_es_exactamente_el_integrando():
    """Prueba exacta de que G(x) = (1/3)ln|x+1| - (1/6)ln(x²-x+1) + (1/√3)·atan((2x-1)/√3) cumple G' = 1/(x³+1) en TODO x ≠ -1:
      d/dx ln|u| = u'/u (a ambos lados de u=0);  d/dx atan(v) = v'/(1+v²)  con v=(2x-1)/√3 → (1/√3)·(2/√3)/(1+(2x-1)²/3) = 1/(2(x²-x+1)).
      G' = 1/(3(x+1)) - (2x-1)/(6(x²-x+1)) + 1/(2(x²-x+1)) = 1/(3(x+1)) + (2-x)/(3(x²-x+1)).  Se comprueba la identidad racional
    en 200 racionales (ambos lados de -1) con Fraction exacta, y simbólicamente por coeficientes: (x²-x+1)+(2-x)(x+1) = 3."""
    for k in range(-300, 300):
        x = Fraction(k, 13)
        if x == -1: continue
        gp = Fraction(1, 3) / (x + 1) - (2 * x - 1) / (6 * (x * x - x + 1)) + Fraction(1, 2) / (x * x - x + 1)
        assert gp == 1 / (x**3 + 1), x
    # (x²-x+1) + (2-x)(x+1) = x²-x+1 + (-x²+x+2) = 3  → G' = 3/(3(x³+1)) = 1/(x³+1)   (coeficientes por polinomio)
    pol = lambda x: (x * x - x + 1) + (2 - x) * (x + 1)
    assert all(pol(Fraction(k)) == 3 for k in range(-20, 21))             # polinomio de grado ≤ 2 constante en ≥3 puntos ⇒ idénticamente 3


@pytest.mark.parametrize("x", [-200.0, -20.0, -3.0, -1.5, -1.05, -0.95, -0.4, 0.0, 0.7, 2.5, 30.0, 400.0])
def test_la_primitiva_del_motor_difiere_de_la_clasica_solo_en_una_constante_por_intervalo(x):
    """Enlaza el texto que devuelve el motor con la primitiva clásica demostrada arriba: F - G es constante en (-∞,-1) y en (-1,∞)."""
    r = call(operation="integrate", expression="1/(x^3+1)")
    F = _F(r["exact_result"])
    G = lambda t: math.log(abs(t + 1)) / 3 - math.log(t * t - t + 1) / 6 + math.atan((2 * t - 1) / math.sqrt(3)) / math.sqrt(3)
    ref = -2.0 if x < -1 else 2.0                                         # punto de referencia del mismo intervalo
    assert abs((F(x) - G(x)) - (F(ref) - G(ref))) < 1e-9
