import pytest
from _soporte import run, F, Matrix, rnd_matrix
import random
import math_universe_linalg.ops as ops


def test_suma_conocida_con_fracciones():
    r = run("matrix_add", [[1, 2], [3, 4]], [["1/2", 0], [0, 1]])
    assert r["status"] == "success_exact" and r["data"]["matrix"] == [["3/2", "2"], ["3", "5"]] and r["verification"]["status"] == "passed"


def test_resta_conocida():
    r = run("matrix_sub", [[5, 7]], [[2, 9]])
    assert r["data"]["matrix"] == [["3", "-2"]] and r["verification"]["status"] == "passed"


@pytest.mark.parametrize("seed", range(20))
def test_propiedades_algebraicas_exactas(seed):
    rng = random.Random(seed); n, m = rng.randint(1, 5), rng.randint(1, 5)
    A, B, C = (rnd_matrix(rng, n, m, frac=True) for _ in range(3))
    Z = Matrix([[0] * m for _ in range(n)])
    assert ops.add(A, B) == ops.add(B, A)                                   # conmutativa
    assert ops.add(ops.add(A, B), C) == ops.add(A, ops.add(B, C))           # asociativa
    assert ops.add(A, Z) == A and ops.sub(A, A) == Z and ops.sub(A, B) == ops.add(A, ops.sub(Z, B))


def test_dimensiones_distintas_es_invalid_input_con_mensaje_claro():
    for op in ("matrix_add", "matrix_sub"):
        r = run(op, [[1, 2]], [[1], [2]])
        assert r["status"] == "invalid_input" and "dimensiones" in r["error"]["message"]


def test_contra_numpy():
    np = pytest.importorskip("numpy")
    rng = random.Random(5)
    for _ in range(100):
        n, m = rng.randint(1, 6), rng.randint(1, 6)
        A, B = rnd_matrix(rng, n, m), rnd_matrix(rng, n, m)
        a, b = np.array(A.tolist(), dtype=float), np.array(B.tolist(), dtype=float)
        assert np.array_equal(np.array(run("matrix_add", A, B)["data"]["matrix"], dtype=float), a + b)
        assert np.array_equal(np.array(run("matrix_sub", A, B)["data"]["matrix"], dtype=float), a - b)
