import pytest, random
from fractions import Fraction
from _soporte import run, Matrix, rnd_matrix
import math_universe_linalg.ops as ops


def test_conocida():
    r = run("matrix_rref", [[1, 2, 3], [2, 4, 6], [1, 0, 1]])
    assert r["data"]["matrix"] == [["1", "0", "1"], ["0", "1", "1"], ["0", "0", "0"]] and r["data"]["pivot_columns"] == [0, 1]
    assert r["verification"]["status"] == "passed"


def test_cuadrada_invertible_da_identidad():
    A = Matrix([[2, 1, 1], [1, 3, 2], [1, 0, 0]])
    assert ops.rref(A)[0] == Matrix.identity(3)


@pytest.mark.parametrize("seed", range(20))
def test_unicidad_e_idempotencia(seed):
    """La RREF es única: rref(P·A) = rref(A) para P invertible, y rref(rref(A)) = rref(A)."""
    rng = random.Random(900 + seed); n, m = rng.randint(1, 6), rng.randint(1, 6)
    A = rnd_matrix(rng, n, m, -4, 4)
    while True:
        P = rnd_matrix(rng, n, n, -3, 3)
        if ops.det(P) != 0: break
    R, piv = ops.rref(A)
    assert ops.rref(ops.mul(P, A))[0] == R
    assert ops.rref(R)[0] == R
    assert len(piv) == ops.rank(A)


def test_contra_numpy_rango_y_pivotes_consistentes():
    np = pytest.importorskip("numpy")
    rng = random.Random(8)
    for _ in range(100):
        A = rnd_matrix(rng, rng.randint(1, 6), rng.randint(1, 6), -4, 4)
        r = run("matrix_rref", A)["data"]
        assert r["rank"] == np.linalg.matrix_rank(np.array(A.tolist(), dtype=float))
