"""Motor 0.6.0: módulos avanzados. Valores de referencia conocidos a mano (no generados por SymPy), verificación
independiente, casos negativos (verificación saboteada, dimensiones, dominio) y respuesta válida según el esquema."""
import pytest

from conftest import call
from math_universe_engine import advanced, steps as STEPS

pytest.importorskip("sympy")
pytest.importorskip("mpmath")


def ok(r):
    assert r["status"] == "success_exact", r
    assert r["verification"]["status"] == "passed", r
    return r


# ---------------- álgebra lineal
def test_autovalores_matriz_simetrica():
    r = ok(call(operation="eigen", structured_input={"a": [[2, 1], [1, 2]]}, latex=True))
    vals = {e["value"]: e for e in r["data"]["eigenvalues"]}
    assert set(vals) == {"1", "3"}
    assert vals["3"]["vectors"] == [["1", "1"]] and vals["1"]["vectors"] == [["-1", "1"]]
    assert r["data"]["diagonalizable"] is True
    assert r["data"]["characteristic_polynomial"].replace(" ", "") == "lambda^2-4*lambda+3"


def test_autovalores_no_diagonalizable():
    r = ok(call(operation="eigen", structured_input={"a": [[1, 1], [0, 1]]}))
    assert r["data"]["eigenvalues"][0]["multiplicity"] == 2 and r["data"]["diagonalizable"] is False


def test_autovalores_complejos():
    r = ok(call(operation="eigen", structured_input={"a": [[0, -1], [1, 0]]}))
    assert {e["value"] for e in r["data"]["eigenvalues"]} == {"-i", "i"}


def test_autovalores_matriz_no_cuadrada():
    assert call(operation="eigen", structured_input={"a": [[1, 2, 3], [4, 5, 6]]})["status"] == "invalid_input"


# ---------------- cálculo multivariable
def test_gradiente():
    r = ok(call(operation="gradient", expression="x^2*y"))
    assert r["data"]["components"] == ["2*x*y", "x^2"]


def test_hessiano():
    r = ok(call(operation="hessian", expression="x^2+x*y+y^2"))
    assert r["data"]["matrix"] == [["2", "1"], ["1", "2"]] and r["data"]["determinant"] == "3"


def test_jacobiano_y_su_determinante():
    r = ok(call(operation="jacobian", expression="x*y; x+y^2", variables=["x", "y"]))
    assert r["data"]["matrix"] == [["y", "x"], ["1", "2*y"]]
    assert r["data"]["determinant"].replace(" ", "") in ("2*y^2-x", "-x+2*y^2")


def test_derivada_parcial_mixta():
    assert ok(call(operation="partial", expression="x^3*y^2", variables=["x", "y"]))["exact_result"] == "6*x^2*y"


# ---------------- series
def test_taylor_seno():
    r = ok(call(operation="series", expression="sin(x)", order=6))
    assert r["exact_result"].replace(" ", "") in ("x^5/120-x^3/6+x", "x-x^3/6+x^5/120")


def test_taylor_polinomio_es_exacto():
    assert ok(call(operation="series", expression="x^2+1", order=4))["exact_result"].replace(" ", "") == "x^2+1"


# ---------------- inecuaciones
def test_inecuacion_cuadratica():
    assert ok(call(operation="inequality", expression="x^2-5*x+6>0"))["exact_result"] == "(-∞, 2) ∪ (3, ∞)"


def test_inecuacion_con_igualdad():
    assert ok(call(operation="inequality", expression="x^2 <= 4"))["exact_result"] == "[-2, 2]"


def test_inecuacion_racional_excluye_el_polo():
    assert ok(call(operation="inequality", expression="1/(x-1) <= 0"))["exact_result"] == "(-∞, 1)"


def test_inecuacion_sin_solucion():
    assert call(operation="inequality", expression="x^2 < -1")["status"] == "no_solution"


# ---------------- complejos
def test_producto_complejo():
    r = ok(call(operation="complex", expression="(2+3*i)*(1-i)"))
    assert r["exact_result"] == "5 + i" and r["data"]["modulus"] == "sqrt(26)"


def test_modulo_y_argumento():
    r = ok(call(operation="complex", expression="3+4*i"))
    assert r["data"]["modulus"] == "5" and r["data"]["conjugate"] == "3 - 4*i"
    r = ok(call(operation="complex", expression="i^2"))
    assert r["exact_result"] == "-1" and r["data"]["argument_degrees"] == "180"


def test_division_compleja_por_cero():
    assert call(operation="complex", expression="1/(i-i)")["status"] in ("domain_error", "invalid_input")


# ---------------- EDO
def test_edo_con_condiciones_iniciales():
    r = ok(call(operation="ode", expression="y''+y=0", conditions=["y(0)=0", "y'(0)=1"]))
    assert r["exact_result"] == "y(x) = sin(x)"


def test_edo_general_tiene_constante():
    r = ok(call(operation="ode", expression="y'=2*y"))
    assert "C1" in r["exact_result"] and "exp(2*x)" in r["exact_result"]


def test_edo_con_variable_t():
    assert ok(call(operation="ode", expression="y'+y=0", conditions=["y(0)=3"]))["exact_result"] == "y(x) = 3*exp(-x)"


# ---------------- Laplace
def test_laplace_exponencial():
    r = ok(call(operation="laplace", expression="exp(3*t)"))
    assert r["exact_result"] == "1/(s - 3)" and "Re(s) > 3" in r["conditions"]


def test_laplace_potencia():
    assert ok(call(operation="laplace", expression="t^2"))["exact_result"] == "2/s^3"


def test_laplace_inversa():
    assert ok(call(operation="inverse_laplace", expression="1/s^2"))["exact_result"] == "t"
    assert ok(call(operation="inverse_laplace", expression="1/(s^2+1)"))["exact_result"] == "sin(t)"


# ---------------- estadística (ejemplo de manual: media 5, desviación poblacional 2)
def test_estadistica_descriptiva():
    d = ok(call(operation="stats", expression="2, 4, 4, 4, 5, 5, 7, 9"))["data"]
    assert d["mean"] == "5" and d["median"] == "9/2" and d["mode"] == ["4"]
    assert d["variance_population"] == "4" and d["std_population"] == "2" and d["variance_sample"] == "32/7"


def test_estadistica_un_dato():
    d = ok(call(operation="stats", expression="7"))["data"]
    assert d["mean"] == "7" and d["variance_sample"] is None


# ---------------- unidades
def test_conversion_de_unidades():
    assert ok(call(operation="units", expression="36 km/h to m/s"))["exact_result"] == "10 m/s"
    assert ok(call(operation="units", expression="1 kWh en J"))["exact_result"] == "3600000 J"


def test_suma_dimensionalmente_incompatible():
    r = call(operation="units", expression="3 m + 2 s")
    assert r["status"] == "domain_error" and "dimensional" in r["error"]["message"]


def test_conversion_entre_dimensiones_distintas():
    assert call(operation="units", expression="5 m to s")["status"] == "domain_error"


def test_unidad_desconocida():
    assert call(operation="units", expression="5 furlong to m")["status"] == "invalid_input"


# ---------------- biblioteca de fórmulas
def test_ley_de_ohm():
    assert ok(call(operation="formula", params={"id": "ohm", "known": {"V": "12", "R": "4"}, "unknown": "I"}))["exact_result"] == "I = 3"


def test_potencia_trifasica():
    r = ok(call(operation="formula", params={"id": "trifasica_p", "known": {"VL": "400", "IL": "10", "fp": "0.8"}, "unknown": "P"}))
    assert r["exact_result"] == "P = 3200*sqrt(3)"


def test_formula_con_datos_incompletos():
    assert call(operation="formula", params={"id": "ohm", "known": {"V": "12"}, "unknown": "I"})["status"] == "invalid_input"


def test_catalogo_de_formulas():
    fs = call(operation="formulas")["data"]["formulas"]
    assert {"ohm", "resonancia", "trifasica_p", "transformador"} <= {f["id"] for f in fs}


# ---------------- verificación saboteada: un resultado falso NO se entrega
def test_autovalor_saboteado_no_se_entrega(monkeypatch):
    import sympy as sp
    real = sp.Matrix.eigenvects
    monkeypatch.setattr(sp.Matrix, "eigenvects", lambda self, **k: [(v + 1, m, vs) for v, m, vs in real(self, **k)])
    r = call(operation="eigen", structured_input={"a": [[2, 1], [1, 2]]})
    assert r["status"] == "internal_error" and r["error"]["code"] == "VERIFICATION_FAILED" and r.get("exact_result") is None


def test_estadistica_saboteada_no_se_entrega(monkeypatch):
    monkeypatch.setattr(advanced.statistics, "fmean", lambda xs: 999.0)
    r = call(operation="stats", expression="1, 2, 3")
    assert r["error"]["code"] == "VERIFICATION_FAILED"


# ---------------- gráficas
def test_grafica_corta_la_asintota():
    d = call(operation="plot", expression="1/x", params={"xmin": -2, "xmax": 2, "samples": 101})["data"]
    segs = d["series"][0]["segments"]
    assert len(segs) == 2                                            # no se une -∞ con +∞
    assert all(p[0] < 0 for p in segs[0]) and all(p[0] > 0 for p in segs[1])


def test_grafica_marca_ceros():
    d = call(operation="plot", expression="x^2-4", params={"xmin": -5, "xmax": 5})["data"]
    assert [round(r, 6) for r in d["series"][0]["roots"]] == [-2.0, 2.0]


def test_grafica_varias_funciones_y_dominio():
    d = call(operation="plot", expression="sqrt(x); sin(x)", params={"xmin": -3, "xmax": 3})["data"]
    assert len(d["series"]) == 2 and min(p[0] for s in d["series"][0]["segments"] for p in s) >= 0


def test_superficie_3d():
    d = call(operation="plot3d", expression="x^2+y^2", params={"xmin": -1, "xmax": 1, "ymin": -1, "ymax": 1, "grid": 11})["data"]
    assert len(d["grid"]) == 11 and d["grid"][5][5] == 0 and d["grid"][0][0] == 2


def test_curva_polar():
    d = call(operation="polar", expression="1", params={"tmin": 0, "tmax": 6.283185307179586})["data"]
    pts = [p for s in d["series"][0]["segments"] for p in s]
    assert all(abs(p[0] ** 2 + p[1] ** 2 - 1) < 1e-9 for p in pts)      # circunferencia unidad


# ---------------- paso a paso (cada secuencia termina en el resultado del motor)
def test_pasos_ecuacion_lineal():
    r = call(operation="solve", expression="2x+3=7", steps=True)
    assert r["exact_result"] == "x = 2" and r["steps"][-1]["latex"] == "x = 2"


def test_pasos_ecuacion_cuadratica():
    s = call(operation="solve", expression="x^2-5*x+6=0", steps=True)["steps"]
    assert any("Discriminante" in p["text"] and r"\left(-5\right)^{2}" in p["latex"] and p["latex"].endswith("= 1") for p in s)
    assert s[-1]["latex"] == r"x = 2,\quad x = 3"


def test_pasos_derivada_regla_del_producto():
    s = call(operation="differentiate", expression="x^3*sin(x)", steps=True)["steps"]
    textos = " ".join(p["text"] for p in s)
    assert "Regla del producto" in textos and "Regla de la potencia" in textos


def test_pasos_gauss_inversa():
    s = call(operation="matrix_inverse", structured_input={"a": [[2, 1], [1, 1]]}, steps=True)["steps"]
    assert s[0]["text"].startswith("Matriz inicial") and r"1 & 0 & 1 & -1" in s[-1]["latex"]


def test_pasos_que_no_cuadran_no_se_muestran():
    assert STEPS.solve_steps("2*x+3=7", None, ["5"]) is None                       # el motor diría 5: no coincide
    assert STEPS.derivative_steps("x^3*sin(x)", None, "3*x^2*cos(x)") is None


def test_sin_steps_no_hay_pasos():
    assert "steps" not in call(operation="solve", expression="2x+3=7")


# ---------------- presentación (LaTeX)
def test_latex_de_entrada_y_resultado():
    r = call(operation="simplify", expression="(x^3-8)/(x-2)", latex=True)
    assert r["latex"]["input"] == r"\frac{x^{3} - 8}{x - 2}" and r["latex"]["result"] == "x^{2} + 2 x + 4"


def test_latex_no_simplifica_al_mostrar():
    from math_universe_engine.presentation import latex_of
    assert latex_of("sqrt(x)^2") == r"\left(\sqrt{x}\right)^{2}"           # no se convierte en x (cambiaría el dominio)


def test_latex_de_sistema_y_matriz():
    from math_universe_engine.presentation import latex_of
    assert latex_of("2*x+y=5; x-y=1").startswith(r"\begin{cases}")
    assert latex_of("[[1, -1/2], [0, 3]]") == r"\begin{pmatrix}1 & - \frac{1}{2} \\ 0 & 3\end{pmatrix}"


# ---------------- lenguaje natural (solo interpreta; nunca calcula)
@pytest.mark.parametrize("frase, op, expr", [
    ("deriva x al cubo por seno de x", "differentiate", "x^3 * sin(x)"),
    ("resuelve x^2-5x+6=0", "solve", "x^2-5x+6=0"),
    ("factoriza x^2-5*x+6", "factor", "x^2-5*x+6"),
    ("raíz cuadrada de 2 más 1", "evaluate", "sqrt(2) + 1"),
])
def test_interpretacion(frase, op, expr):
    d = call(operation="interpret", expression=frase)["data"]
    assert d["understood"] and d["operation"] == op and d["expression"] == expr and "exact_result" not in d


def test_interpretacion_despeje_y_limite():
    d = call(operation="interpret", expression="despeja R en V = I*R")["data"]
    assert d["operation"] == "solve" and d["variables"] == ["R"]
    d = call(operation="interpret", expression="límite de sin(x)/x cuando x tiende a 0")["data"]
    assert d["operation"] == "limit" and d["point"] == "0" and d["expression"] == "sin(x)/x"


def test_interpretacion_no_entendida():
    d = call(operation="interpret", expression="hola qué tal")["data"]
    assert d["understood"] is False and "Ejemplos" in d["summary"]
