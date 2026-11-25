import pytest, random
from _soporte import run, Matrix, rnd_matrix
import math_universe_linalg.ops as ops


def test_transpuesta_conocida_no_cuadrada():
    r = run("matrix_transpose", [[1, 2, 3], [4, 5, 6]])
    assert r["data"]["matrix"] == [["1", "4"], ["2", "5"], ["3", "6"]] and r["verification"]["status"] == "passed"


def test_vector_fila_y_1x1():
    assert run("matrix_transpose", [[1, 2, 3]])["data"]["matrix"] == [["1"], ["2"], ["3"]]
    assert run("matrix_transpose", [["7/2"]])["data"]["matrix"] == [["7/2"]]


@pytest.mark.parametrize("seed", range(15))
def test_involucion_y_linealidad(seed):
    rng = random.Random(seed); n, m = rng.randint(1, 6), rng.randint(1, 6)
    A, B = rnd_matrix(rng, n, m, frac=True), rnd_matrix(rng, n, m, frac=True)
    assert ops.transpose(ops.transpose(A)) == A
    assert ops.transpose(ops.add(A, B)) == ops.add(ops.transpose(A), ops.transpose(B))
    assert ops.transpose(A).shape == (m, n)


def test_contra_numpy():
    np = pytest.importorskip("numpy")
    rng = random.Random(3)
    for _ in range(100):
        A = rnd_matrix(rng, rng.randint(1, 7), rng.randint(1, 7))
        assert np.array_equal(np.array(run("matrix_transpose", A)["data"]["matrix"], dtype=float), np.array(A.tolist(), dtype=float).T)
