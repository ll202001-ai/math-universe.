import pytest, random
from _soporte import run, Matrix, rnd_matrix
import math_universe_linalg.ops as ops


def rank(A): return run("matrix_rank", A)


def test_casos_conocidos():
    assert rank([[1, 2, 3], [2, 4, 6], [1, 0, 1]])["data"]["rank"] == 2
    assert rank([[0, 0], [0, 0]])["data"]["rank"] == 0
    assert rank([[1, 0], [0, 1]])["data"]["rank"] == 2
    assert rank([[1, 2, 3]])["data"]["rank"] == 1 and rank([[1], [2], [3]])["data"]["rank"] == 1
    assert rank([[0]])["data"]["rank"] == 0 and rank([[5]])["data"]["rank"] == 1


def test_certificado_de_rango_presente_y_verificado():
    r = rank([[1, 2, 3, 4], [2, 4, 6, 8], [1, 0, 1, 0]])
    assert r["data"]["rank"] == 2 and r["data"]["nullity"] == 2 and r["verification"]["status"] == "passed"
    assert "menor" in r["verification"]["method"]


@pytest.mark.parametrize("seed", range(25))
def test_rango_por_construccion(seed):
    """Verdad de terreno SIN NumPy: A = B·C con B = [I_r; X] (n×r) y C = [I_r | Y] (r×m) tiene rango exactamente r."""
    rng = random.Random(seed); n, m = rng.randint(2, 7), rng.randint(2, 7); r = rng.randint(0, min(n, m))
    B = Matrix([[1 if i == j else 0 for j in range(r)] if i < r else [rng.randint(-5, 5) for _ in range(r)] for i in range(n)]) if r else None
    C = Matrix([[1 if i == j else 0 for j in range(r)] + [rng.randint(-5, 5) for _ in range(m - r)] for i in range(r)]) if r else None
    A = ops.mul(B, C) if r else Matrix([[0] * m for _ in range(n)])
    assert run("matrix_rank", A)["data"]["rank"] == r


@pytest.mark.parametrize("seed", range(15))
def test_propiedades(seed):
    rng = random.Random(500 + seed); n, m, p = (rng.randint(1, 6) for _ in range(3))
    A, B = rnd_matrix(rng, n, m, -3, 3), rnd_matrix(rng, m, p, -3, 3)
    assert ops.rank(A) == ops.rank(ops.transpose(A)) <= min(n, m)
    assert ops.rank(ops.mul(A, B)) <= min(ops.rank(A), ops.rank(B))
    assert ops.rank(A) + (m - ops.rank(A)) == m                              # rango + nulidad = nº columnas


def test_contra_numpy():
    np = pytest.importorskip("numpy")
    rng = random.Random(41)
    for _ in range(300):
        n, m = rng.randint(1, 7), rng.randint(1, 7)
        A = rnd_matrix(rng, n, m, -4, 4)
        if rng.random() < 0.5 and n > 1: A = Matrix([A.tolist()[0]] + [[2 * x for x in A.tolist()[0]]] + A.tolist()[2:]) if n >= 2 else A
        assert run("matrix_rank", A)["data"]["rank"] == np.linalg.matrix_rank(np.array(A.tolist(), dtype=float))
