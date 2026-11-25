"""Pruebas aleatorias con semillas fijas: el módulo (exacto) frente a NumPy (oráculo flotante, no dependencia). Toda operación debe pasar su
verificación interna Y coincidir con NumPy; nada se omite en silencio (los casos mal condicionados se CUENTAN y se exige un mínimo)."""
import random
import pytest
from fractions import Fraction
from _soporte import run, Matrix, rnd_matrix


def num(rows): return [[float(Fraction(x)) for x in r] for r in rows]


@pytest.mark.parametrize("seed", [1, 7, 99, 2024, 31337])
def test_fuzz_todas_las_operaciones(seed):
    np = pytest.importorskip("numpy")
    rng = random.Random(seed); cnt = {"det": 0, "inv": 0, "solve": 0, "rank": 0, "mul": 0, "singular": 0, "mal_condicionadas": 0}
    for _ in range(120):
        n = rng.randint(1, 6); frac = rng.random() < 0.4
        A = rnd_matrix(rng, n, n, -9, 9, frac=frac); B = rnd_matrix(rng, n, n, -9, 9, frac=frac); b = rnd_matrix(rng, n, 1, -9, 9, frac=frac)
        a = np.array(num(A.rows))
        # producto y suma
        r = run("matrix_mul", A, B); assert r["verification"]["status"] == "passed"
        assert np.allclose(np.array(num([[Fraction(x) for x in row] for row in r["data"]["matrix"]])), a @ np.array(num(B.rows)), rtol=1e-10, atol=1e-10); cnt["mul"] += 1
        # determinante
        r = run("matrix_det", A); assert r["verification"]["status"] == "passed"
        d = float(Fraction(r["data"]["determinant"])); nd = float(np.linalg.det(a))
        assert abs(d - nd) <= 1e-8 * (1 + abs(nd)), (A.tolist(), d, nd); cnt["det"] += 1
        # rango
        r = run("matrix_rank", A); assert r["verification"]["status"] == "passed"
        if not frac: assert r["data"]["rank"] == np.linalg.matrix_rank(a); cnt["rank"] += 1
        # inversa / sistema
        singular = d == 0
        ri = run("matrix_inverse", A); rs = run("matrix_solve", A, b)
        if singular:
            assert ri["status"] == "domain_error" and ri["error"]["details"]["null_vector"]; cnt["singular"] += 1
            assert rs["status"] in ("multiple_solutions", "no_solution") and rs["verification"]["status"] == "passed"
        else:
            assert ri["status"] == "success_exact" and ri["verification"]["status"] == "passed"
            assert rs["status"] == "success_exact" and rs["verification"]["status"] == "passed"
            if np.linalg.cond(a) > 1e8: cnt["mal_condicionadas"] += 1; continue
            inv = np.array(num([[Fraction(x) for x in row] for row in ri["data"]["matrix"]]))
            assert np.allclose(inv, np.linalg.inv(a), rtol=1e-7, atol=1e-9); cnt["inv"] += 1
            x = np.array([float(Fraction(t)) for t in rs["data"]["particular"]])
            assert np.allclose(x, np.linalg.solve(a, np.array(num(b.rows)).ravel()), rtol=1e-7, atol=1e-9); cnt["solve"] += 1
    assert cnt["det"] == 120 and cnt["mul"] == 120 and cnt["inv"] > 50 and cnt["solve"] > 50, cnt


@pytest.mark.parametrize("seed", [3, 11, 4242])
def test_fuzz_rectangulares_rango_y_sistemas(seed):
    np = pytest.importorskip("numpy")
    rng = random.Random(seed)
    for _ in range(150):
        m, n = rng.randint(1, 7), rng.randint(1, 7)
        A = rnd_matrix(rng, m, n, -4, 4); b = rnd_matrix(rng, m, 1, -4, 4)
        a = np.array(num(A.rows)); bb = np.array(num(b.rows)).ravel()
        assert run("matrix_rank", A)["data"]["rank"] == np.linalg.matrix_rank(a)
        rs = run("matrix_solve", A, b); assert rs["verification"]["status"] == "passed"
        x, _, _, _ = np.linalg.lstsq(a, bb, rcond=None)
        consistente = np.linalg.norm(a @ x - bb) < 1e-7
        assert (rs["status"] != "no_solution") == consistente, (A.tolist(), b.tolist())
        rr = run("matrix_rref", A); assert rr["verification"]["status"] == "passed" and rr["data"]["rank"] == np.linalg.matrix_rank(a)
