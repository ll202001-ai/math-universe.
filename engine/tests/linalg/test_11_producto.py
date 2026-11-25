import pytest, random
from _soporte import run, Matrix, rnd_matrix
import math_universe_linalg.ops as ops


def test_producto_conocido_y_no_conmutativo():
    A, B = [[1, 2], [3, 4]], [[0, 1], [1, 0]]
    assert run("matrix_mul", A, B)["data"]["matrix"] == [["2", "1"], ["4", "3"]]
    assert run("matrix_mul", B, A)["data"]["matrix"] == [["3", "4"], ["1", "2"]]


def test_producto_no_cuadrado_y_vector():
    r = run("matrix_mul", [[1, 2, 3], [4, 5, 6]], [[1], [0], [-1]])
    assert r["data"]["matrix"] == [["-2"], ["-2"]] and r["verification"]["status"] == "passed"


def test_identidad_y_cero():
    A = Matrix([["1/3", 2], [5, "-7/4"]])
    assert ops.mul(A, Matrix.identity(2)) == A == ops.mul(Matrix.identity(2), A)
    assert ops.mul(A, Matrix([[0, 0], [0, 0]])) == Matrix([[0, 0], [0, 0]])


@pytest.mark.parametrize("seed", range(20))
def test_propiedades_exactas(seed):
    rng = random.Random(100 + seed); n, m, p, q = (rng.randint(1, 5) for _ in range(4))
    A, B, C = rnd_matrix(rng, n, m, frac=True), rnd_matrix(rng, m, p, frac=True), rnd_matrix(rng, p, q, frac=True)
    assert ops.mul(ops.mul(A, B), C) == ops.mul(A, ops.mul(B, C))                              # asociativa
    assert ops.transpose(ops.mul(A, B)) == ops.mul(ops.transpose(B), ops.transpose(A))        # (AB)ᵀ = BᵀAᵀ
    B2 = rnd_matrix(rng, m, p, frac=True)
    assert ops.mul(A, ops.add(B, B2)) == ops.add(ops.mul(A, B), ops.mul(A, B2))               # distributiva


def test_dimensiones_incompatibles():
    r = run("matrix_mul", [[1, 2]], [[1, 2]])
    assert r["status"] == "invalid_input" and "columnas" in r["error"]["message"]


def test_contra_numpy_exacto_en_enteros():
    np = pytest.importorskip("numpy")
    rng = random.Random(9)
    for _ in range(150):
        n, m, p = (rng.randint(1, 7) for _ in range(3))
        A, B = rnd_matrix(rng, n, m), rnd_matrix(rng, m, p)
        got = np.array(run("matrix_mul", A, B)["data"]["matrix"], dtype=object).astype(float)
        assert np.array_equal(got, np.array(A.tolist(), dtype=np.int64) @ np.array(B.tolist(), dtype=np.int64))


def test_contra_numpy_con_fracciones_tolerancia_flotante():
    np = pytest.importorskip("numpy")
    rng = random.Random(10)
    for _ in range(80):
        A, B = rnd_matrix(rng, 4, 3, frac=True), rnd_matrix(rng, 3, 5, frac=True)
        got = np.array([[float(__import__("fractions").Fraction(x)) for x in r] for r in run("matrix_mul", A, B)["data"]["matrix"]])
        assert np.allclose(got, np.array([[float(x) for x in r] for r in A.rows]) @ np.array([[float(x) for x in r] for r in B.rows]), rtol=1e-12, atol=1e-12)
