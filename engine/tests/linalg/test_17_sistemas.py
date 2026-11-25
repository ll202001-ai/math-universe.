import pytest, random
from fractions import Fraction
from _soporte import run, Matrix, rnd_matrix
import math_universe_linalg.ops as ops


def col(*xs): return [[x] for x in xs]


def test_unica():
    r = run("matrix_solve", [[1, 1], [1, -1]], col(3, 1))
    assert r["status"] == "success_exact" and r["data"]["particular"] == ["2", "1"] and r["data"]["nullspace_basis"] == []
    assert r["verification"]["status"] == "passed"


def test_infinitas_con_base_del_nucleo():
    r = run("matrix_solve", [[1, 1, 1], [0, 1, -1]], col(6, 1))
    assert r["status"] == "multiple_solutions" and r["data"]["rank"] == 2 and len(r["data"]["nullspace_basis"]) == 1
    A = Matrix([[1, 1, 1], [0, 1, -1]]); x0 = [Fraction(v) for v in r["data"]["particular"]]
    v = [Fraction(t) for t in r["data"]["nullspace_basis"][0]]
    for t in (-3, 0, Fraction(5, 2), 100):                                  # TODA la recta x0 + t·v resuelve el sistema
        x = [a + t * b for a, b in zip(x0, v)]
        assert [sum((p * q for p, q in zip(row, x)), Fraction(0)) for row in A.rows] == [6, 1]


def test_sin_solucion_con_certificado_de_farkas():
    r = run("matrix_solve", [[1, 1], [2, 2]], col(3, 7))
    assert r["status"] == "no_solution" and r["verification"]["status"] == "passed"
    y = [Fraction(t) for t in r["data"]["certificate_y"]]
    A = [[1, 1], [2, 2]]; b = [3, 7]
    assert all(sum(y[i] * A[i][j] for i in range(2)) == 0 for j in range(2)) and sum(y[i] * b[i] for i in range(2)) != 0


def test_sobredeterminado_consistente_e_inconsistente():
    A = [[1, 0], [0, 1], [1, 1]]
    assert run("matrix_solve", A, col(1, 2, 3))["status"] == "success_exact"
    assert run("matrix_solve", A, col(1, 2, 4))["status"] == "no_solution"


def test_subdeterminado_y_homogeneo():
    r = run("matrix_solve", [[1, 2, 3]], col(0))
    assert r["status"] == "multiple_solutions" and len(r["data"]["nullspace_basis"]) == 2
    r = run("matrix_solve", [[2, 0], [0, 3]], col(0, 0))
    assert r["data"]["particular"] == ["0", "0"] and r["status"] == "success_exact"


def test_dimensiones_y_b_no_columna():
    assert run("matrix_solve", [[1, 2], [3, 4]], col(1, 2, 3))["status"] == "invalid_input"
    assert run("matrix_solve", [[1, 2], [3, 4]], [[1, 2], [3, 4]])["status"] == "invalid_input"


@pytest.mark.parametrize("seed", range(30))
def test_construido_con_solucion_conocida(seed):
    """Verdad de terreno SIN NumPy: b = A·x0 ⇒ el sistema es consistente y x0 lo resuelve; b + e (e fuera del espacio columna) no."""
    rng = random.Random(seed); m, n = rng.randint(1, 6), rng.randint(1, 6)
    A = rnd_matrix(rng, m, n, -5, 5); x0 = [Fraction(rng.randint(-6, 6), rng.randint(1, 3)) for _ in range(n)]
    b = Matrix([[sum((A.rows[i][j] * x0[j] for j in range(n)), Fraction(0))] for i in range(m)])
    r = run("matrix_solve", A, b)
    assert r["status"] in ("success_exact", "multiple_solutions") and r["verification"]["status"] == "passed"
    if r["status"] == "success_exact": assert [Fraction(t) for t in r["data"]["particular"]] == x0


def test_contra_numpy_sistemas_cuadrados():
    np = pytest.importorskip("numpy")
    rng = random.Random(61); hechos = 0
    for _ in range(250):
        n = rng.randint(1, 7); A = rnd_matrix(rng, n, n); b = rnd_matrix(rng, n, 1)
        a = np.array(A.tolist(), dtype=float)
        if abs(np.linalg.det(a)) < 0.5 or np.linalg.cond(a) > 1e8: continue
        r = run("matrix_solve", A, b)
        assert r["status"] == "success_exact"
        got = np.array([float(Fraction(t)) for t in r["data"]["particular"]])
        assert np.allclose(got, np.linalg.solve(a, np.array(b.tolist(), dtype=float).ravel()), rtol=1e-8, atol=1e-9); hechos += 1
    assert hechos > 100


def test_contra_numpy_inconsistentes_tienen_residuo_positivo():
    np = pytest.importorskip("numpy")
    rng = random.Random(62); vistos = 0
    for _ in range(300):
        m, n = rng.randint(2, 6), rng.randint(1, 4)
        A = rnd_matrix(rng, m, n, -4, 4); b = rnd_matrix(rng, m, 1, -4, 4)
        r = run("matrix_solve", A, b)
        x, res, rk, _ = np.linalg.lstsq(np.array(A.tolist(), dtype=float), np.array(b.tolist(), dtype=float).ravel(), rcond=None)
        resid = np.linalg.norm(np.array(A.tolist(), dtype=float) @ x - np.array(b.tolist(), dtype=float).ravel())
        assert (r["status"] == "no_solution") == (resid > 1e-7), (A.tolist(), b.tolist(), resid, r["status"])
        vistos += r["status"] == "no_solution"
    assert vistos > 20
