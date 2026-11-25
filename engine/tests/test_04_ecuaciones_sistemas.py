"""Ecuaciones de una variable, sistemas lineales y despeje literal."""
import pytest
from conftest import call


@pytest.mark.parametrize("eq,exp", [
    ("2x+5=15", "x = 5"), ("x^2-5x+6=0", "x = 2, x = 3"), ("x^2=4", "x = -2, x = 2"),
    ("x^3-6x^2+11x-6=0", "x = 1, x = 2, x = 3"), ("2x^2-3x-2=0", "x = -1/2, x = 2"),
    ("x^2-2=0", "x = -sqrt(2), x = sqrt(2)"), ("x^2-x-1=0", "x = 1/2 - (1/2)*sqrt(5), x = 1/2 + (1/2)*sqrt(5)"),
    ("x^4-5x^2+4=0", "x = -2, x = -1, x = 1, x = 2"), ("x^2-2x+1=0", "x = 1"),
    ("(x-1)(x-2)(x-3)=0", "x = 1, x = 2, x = 3"), ("1/x=2", "x = 1/2"), ("x+1/x=2", "x = 1"),
    ("x^2=0", "x = 0"), ("3x=0", "x = 0"), ("x/2+x/3=5", "x = 6"),
    ("x^4+x^2+1=0", None),
])
def test_ecuaciones(eq, exp):
    r = call(operation="solve", expression=eq)
    if exp is None:
        assert r["status"] == "no_solution"; return
    assert r["status"] == "success_exact", r
    assert r["exact_result"] == exp
    assert r["verification"]["status"] == "passed"


def test_pdf_x2_5x_6_se_sustituyen_las_raices():
    r = call(operation="solve", expression="x^2-5x+6=0")
    assert r["verification"] == {"status": "passed", "method": "sustitucion_exacta_en_la_ecuacion_original"}
    assert [s["value"] for s in r["data"]["solutions"]] == ["2", "3"]


def test_multiplicidad():
    r = call(operation="solve", expression="x^2-2x+1=0")
    assert r["data"]["solutions"][0]["multiplicity"] == 2


def test_identidad_y_contradiccion():
    assert call(operation="solve", expression="x+1=x+1")["status"] == "multiple_solutions"
    assert call(operation="solve", expression="x+1=x+2")["status"] == "no_solution"


def test_cubica_irreducible_no_soportada_no_se_inventa():
    r = call(operation="solve", expression="x^3-2=0")
    assert r["status"] == "unsupported" and r["error"]["code"] == "NOT_SOLVED"


def test_variable_ambigua():
    assert call(operation="solve", expression="x+y=3")["status"] == "invalid_input"
    # Un enunciado sin incógnitas se decide con aritmética exacta (ver test_09_auditoria)
    r = call(operation="solve", expression="3=3")
    assert r["status"] == "success_exact" and r["exact_result"] == "Verdadero"


# ---------------- sistemas ----------------
def test_sistema_unico_pdf():
    r = call(operation="solve", expression="2x+y=5; x-y=1")
    assert r["status"] == "success_exact" and r["exact_result"] == "x = 2, y = 1"
    d = r["data"]
    assert d["coefficient_matrix"] == [["2", "1"], ["1", "-1"]]
    assert d["augmented_matrix"] == [["2", "1", "5"], ["1", "-1", "1"]]
    assert d["rank_A"] == 2 and d["rank_augmented"] == 2
    assert r["verification"]["status"] == "passed"


def test_sistema_3x3():
    r = call(operation="solve", expression="x+y+z=6; x-y=1; y+z=4")
    assert r["exact_result"] == "x = 2, y = 1, z = 3" and r["data"]["rank_A"] == 3


def test_sistema_infinitas_soluciones():
    r = call(operation="solve", expression="x+y=2; 2x+2y=4")
    assert r["status"] == "multiple_solutions" and r["data"]["rank_A"] == 1 == r["data"]["rank_augmented"]
    assert r["data"]["free_variables"] == ["y"] and r["verification"]["status"] == "passed"


def test_sistema_subdeterminado_3_incognitas():
    r = call(operation="solve", expression="x+y+z=6; x-y=1")
    assert r["status"] == "multiple_solutions" and r["data"]["free_variables"] == ["z"]
    assert r["verification"]["status"] == "passed"


def test_sistema_incompatible():
    r = call(operation="solve", expression="x+y=2; x+y=3")
    assert r["status"] == "no_solution"
    assert r["data"]["rank_A"] == 1 and r["data"]["rank_augmented"] == 2
    assert r["verification"]["status"] == "passed"


def test_sistema_sobredeterminado_consistente_e_inconsistente():
    assert call(operation="solve", expression="x+y=3; x-y=1; 2x=4")["exact_result"] == "x = 2, y = 1"
    assert call(operation="solve", expression="x+y=3; x-y=1; 2x=5")["status"] == "no_solution"


def test_sistema_con_fracciones_y_coeficientes_negativos():
    r = call(operation="solve", expression="x/2+y/3=1; x-y=-1/2")
    assert r["status"] == "success_exact" and r["verification"]["status"] == "passed"


def test_sistema_no_lineal_no_soportado():
    r = call(operation="solve", expression="x^2+y=3; x-y=1", variables=["x", "y"])
    assert r["status"] == "unsupported"


def test_sistema_con_supuesto_que_la_solucion_incumple():
    assert call(operation="solve", expression="x+y=1; x-y=3", assumptions={"y": "positive"})["status"] == "no_solution"


# ---------------- despeje literal ----------------
@pytest.mark.parametrize("eq,var,exp,cond", [
    ("V=I*R", "R", "R = V/I", "I ≠ 0"), ("V=I*R", "I", "I = V/R", "R ≠ 0"), ("P=V*I", "V", "V = P/I", "I ≠ 0"),
    ("F=m*a", "a", "a = F/m", "m ≠ 0"), ("a*x+b=c", "x", "x = (-b + c)/a", "a ≠ 0"),
    ("y=m*x+b", "x", "x = (-b + y)/m", "m ≠ 0"), ("1/R=1/R1+1/R2", "R", "R = R1*R2/(R1 + R2)", "R1 + R2 ≠ 0"),
])
def test_despeje(eq, var, exp, cond):
    r = call(operation="solve", expression=eq, variables=[var])
    if exp is None:
        assert r["status"] in ("success_exact", "unsupported"); return
    assert r["exact_result"] == exp and cond in r["conditions"] and r["verification"]["status"] == "passed"


def test_despeje_grado_2_no_soportado():
    assert call(operation="solve", expression="x^2=a", variables=["x"])["status"] == "unsupported"
