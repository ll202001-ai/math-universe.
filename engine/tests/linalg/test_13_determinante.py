import pytest, random
from fractions import Fraction
from _soporte import run, Matrix, rnd_matrix
import math_universe_linalg.ops as ops
import math_universe_linalg.checks as ck


def det(A): return Fraction(run("matrix_det", A)["data"]["determinant"])


def test_2x2_y_3x3_conocidos():
    assert det([[1, 2], [3, 4]]) == -2
    assert det([[2, 0, 1], [1, 3, 2], [1, 1, 1]]) == 0
    assert det([[6, 1, 1], [4, -2, 5], [2, 8, 7]]) == -306                 # valor clásico (regla de Sarrus)


def test_triangular_es_producto_de_la_diagonal():
    assert det([[2, 5, 7, 1], [0, "3/2", 4, 9], [0, 0, -4, 2], [0, 0, 0, 5]]) == 2 * Fraction(3, 2) * -4 * 5


@pytest.mark.parametrize("n", [2, 3, 4, 5, 6])
def test_vandermonde_formula_cerrada(n):
    xs = [Fraction(k * k + 1, k + 2) for k in range(n)]
    V = Matrix([[x ** j for j in range(n)] for x in xs])
    esperado = Fraction(1)
    for i in range(n):
        for j in range(i + 1, n): esperado *= xs[j] - xs[i]
    assert det(V) == esperado


@pytest.mark.parametrize("n,esperado", [(2, Fraction(1, 12)), (3, Fraction(1, 2160)), (4, Fraction(1, 6048000))])
def test_hilbert_valores_publicados(n, esperado):
    assert det(Matrix([[Fraction(1, i + j + 1) for j in range(n)] for i in range(n)])) == esperado


@pytest.mark.parametrize("seed", range(20))
def test_propiedades_exactas(seed):
    rng = random.Random(seed); n = rng.randint(1, 6)
    A, B = rnd_matrix(rng, n, n, frac=True), rnd_matrix(rng, n, n, frac=True)
    assert ops.det(ops.mul(A, B)) == ops.det(A) * ops.det(B)                # multiplicativa
    assert ops.det(ops.transpose(A)) == ops.det(A)
    if n >= 2:
        rows = A.tolist(); rows[0], rows[1] = rows[1], rows[0]
        assert ops.det(Matrix(rows)) == -ops.det(A)                         # intercambio de filas cambia el signo
        rows = A.tolist(); rows[0] = [3 * x for x in rows[0]]
        assert ops.det(Matrix(rows)) == 3 * ops.det(A)                      # escalar una fila
        rows = A.tolist(); rows[1] = list(rows[0])
        assert ops.det(Matrix(rows)) == 0                                   # dos filas iguales


def test_algoritmos_distintos_coinciden():
    rng = random.Random(77)
    for _ in range(100):
        n = rng.randint(1, 6); A = rnd_matrix(rng, n, n, frac=True)
        assert ops.det(A) == ck.det_bareiss(A) == ck.det_laplace(A)


def test_no_cuadrada_es_invalid_input():
    r = run("matrix_det", [[1, 2, 3], [4, 5, 6]])
    assert r["status"] == "invalid_input" and "cuadrada" in r["error"]["message"]


def test_singular_avisa():
    r = run("matrix_det", [[1, 2], [2, 4]])
    assert r["data"]["determinant"] == "0" and r["data"]["invertible"] is False and r["warnings"]


def test_contra_numpy():
    np = pytest.importorskip("numpy")
    rng = random.Random(21)
    for _ in range(200):
        n = rng.randint(1, 8); A = rnd_matrix(rng, n, n)
        exacto = det(A); num = np.linalg.det(np.array(A.tolist(), dtype=float))
        assert exacto.denominator == 1
        assert abs(float(exacto) - num) <= 1e-8 * (1 + abs(num)), (A.tolist(), exacto, num)
