import pytest, random
from fractions import Fraction
from _soporte import run, Matrix, rnd_matrix
import math_universe_linalg.ops as ops


def inv(A): return run("matrix_inverse", A)


def test_2x2_formula_cerrada():
    r = inv([[2, 1], [1, 1]])
    assert r["data"]["matrix"] == [["1", "-1"], ["-1", "2"]] and r["verification"]["status"] == "passed"
    a, b, c, d = 3, 5, 2, 4; det = a * d - b * c
    assert inv([[a, b], [c, d]])["data"]["matrix"] == [[str(Fraction(d, det)), str(Fraction(-b, det))], [str(Fraction(-c, det)), str(Fraction(a, det))]]


def test_hilbert_3_tiene_inversa_entera_publicada():
    H = Matrix([[Fraction(1, i + j + 1) for j in range(3)] for i in range(3)])
    assert inv(H)["data"]["matrix"] == [["9", "-36", "30"], ["-36", "192", "-180"], ["30", "-180", "180"]]


def test_singular_da_domain_error_con_certificado_comprobable():
    A = Matrix([[1, 2, 3], [2, 4, 6], [1, 0, 1]])
    r = inv(A)
    assert r["status"] == "domain_error" and "singular" in r["error"]["message"]
    v = [Fraction(x) for x in r["error"]["details"]["null_vector"]]
    assert any(v) and all(sum((x * y for x, y in zip(row, v)), Fraction(0)) == 0 for row in A.rows)      # A·v = 0, v ≠ 0


def test_no_cuadrada_invalid_input():
    assert inv([[1, 2, 3], [4, 5, 6]])["status"] == "invalid_input"


@pytest.mark.parametrize("seed", range(20))
def test_propiedades_exactas(seed):
    rng = random.Random(seed); n = rng.randint(1, 5)
    while True:
        A, B = rnd_matrix(rng, n, n, frac=True), rnd_matrix(rng, n, n, frac=True)
        if ops.det(A) != 0 and ops.det(B) != 0: break
    I = Matrix.identity(n)
    assert ops.mul(A, ops.inverse(A)) == I == ops.mul(ops.inverse(A), A)
    assert ops.inverse(ops.inverse(A)) == A
    assert ops.inverse(ops.mul(A, B)) == ops.mul(ops.inverse(B), ops.inverse(A))
    assert ops.inverse(ops.transpose(A)) == ops.transpose(ops.inverse(A))
    assert ops.det(ops.inverse(A)) == 1 / ops.det(A)


def test_inversa_de_identidad_y_1x1():
    assert inv([[1, 0], [0, 1]])["data"]["matrix"] == [["1", "0"], ["0", "1"]]
    assert inv([["-4"]])["data"]["matrix"] == [["-1/4"]]
    assert inv([[0]])["status"] == "domain_error"


def test_contra_numpy():
    np = pytest.importorskip("numpy")
    rng = random.Random(31); n_ok = 0
    for _ in range(200):
        n = rng.randint(1, 7); A = rnd_matrix(rng, n, n)
        a = np.array(A.tolist(), dtype=float)
        if abs(np.linalg.det(a)) < 0.5:                      # singular (det entero ⇒ 0) o casi: el motor decide exacto
            assert (run("matrix_inverse", A)["status"] == "domain_error") == (round(np.linalg.det(a)) == 0)
            continue
        if np.linalg.cond(a) > 1e8: continue
        r = run("matrix_inverse", A)
        assert r["status"] == "success_exact"
        got = np.array([[float(Fraction(x)) for x in row] for row in r["data"]["matrix"]])
        assert np.allclose(got, np.linalg.inv(a), rtol=1e-8, atol=1e-10); n_ok += 1
    assert n_ok > 100
