"""Los verificadores NO son vacuos: rechazan resultados falsos. Y si el algoritmo principal se sabotea, run() lo declara VERIFICATION_FAILED."""
import pytest
from fractions import Fraction
from _soporte import run, Matrix
import math_universe_linalg.checks as ck
import math_universe_linalg.ops as ops
import math_universe_linalg.api as api

A = Matrix([[1, 2], [3, 4]]); B = Matrix([[0, 1], [1, 0]])


def test_verificadores_rechazan_lo_falso():
    assert ck.check_add(A, B, ops.add(A, B)) and not ck.check_add(A, B, Matrix([[1, 3], [4, 5]]))
    assert ck.check_sub(A, B, ops.sub(A, B)) and not ck.check_sub(A, B, ops.add(A, B))
    assert ck.check_mul(A, B, ops.mul(A, B)) and not ck.check_mul(A, B, ops.mul(B, A)) and not ck.check_mul(A, B, Matrix([[2, 1], [4, 4]]))
    assert ck.check_transpose(A, ops.transpose(A)) and not ck.check_transpose(A, A)
    assert ck.check_det(A, Fraction(-2)) and not ck.check_det(A, Fraction(2)) and not ck.check_det(A, Fraction(0))
    assert ck.check_inverse(A, ops.inverse(A)) and not ck.check_inverse(A, A) and not ck.check_inverse(A, Matrix([[-2, 1], [Fraction(3, 2), Fraction(1, 2)]]))


def test_verificador_de_rango_rechaza_rango_falso():
    S = Matrix([[1, 2, 3], [2, 4, 6], [1, 0, 1]])                     # rango 2
    R, piv = ops.rref(S); null = ops._null_vectors(R.tolist(), piv, 3)
    assert ck.check_rank(S, 2, piv, [0, 2], null) is True            # certificado correcto: filas 0 y 2 independientes, nulidad 1
    assert not ck.check_rank(S, 3, [0, 1, 2], [0, 1, 2], [])          # rango 3: el menor 3×3 es nulo
    assert not ck.check_rank(S, 1, [0], [0], null[:2] if len(null) > 1 else [[1, 0, 0], [0, 1, 0]])   # rango 1 falso: sin nulidad suficiente
    assert not ck.check_rank(S, 2, piv, [0, 1], null)                 # filas 0 y 1 son dependientes: el menor es nulo


def test_verificador_de_sistemas_rechaza_soluciones_falsas():
    a = Matrix([[1, 1], [1, -1]]); b = Matrix([[3], [1]])
    ok = ops.solve(a, b)
    assert ck.check_solve(a, b, ok)
    mal = dict(ok); mal["particular"] = [Fraction(2), Fraction(2)]
    assert not ck.check_solve(a, b, mal)
    s = Matrix([[1, 1], [2, 2]]); bb = Matrix([[3], [7]]); res = ops.solve(s, bb)
    assert res["kind"] == "none" and ck.check_solve(s, bb, res)
    malc = dict(res); malc["certificate"] = [Fraction(0), Fraction(0)]            # yᵀb = 0: no es certificado
    assert not ck.check_solve(s, bb, malc)
    malc2 = dict(res); malc2["certificate"] = [Fraction(1), Fraction(0)]          # yᵀA ≠ 0
    assert not ck.check_solve(s, bb, malc2)


@pytest.mark.parametrize("op,patch,arg_a,arg_b", [
    ("matrix_det", ("det", lambda a: Fraction(12345)), [[1, 2], [3, 4]], None),
    ("matrix_mul", ("mul", lambda a, b: Matrix([[0, 0], [0, 0]])), [[1, 2], [3, 4]], [[1, 0], [0, 1]]),
    ("matrix_inverse", ("inverse", lambda a: a), [[2, 1], [1, 1]], None),
    ("matrix_add", ("add", lambda a, b: a), [[1, 2]], [[3, 4]]),
])
def test_si_el_algoritmo_principal_falla_se_declara_verification_failed(monkeypatch, op, patch, arg_a, arg_b):
    monkeypatch.setattr(ops, patch[0], patch[1])
    r = run(op, arg_a, arg_b)
    assert r["status"] == "internal_error" and r["error"]["code"] == "VERIFICATION_FAILED"
    assert r["verification"]["status"] == "failed" and "unverified_result" in r["error"]["details"]
    assert r["exact_result"] is None                                    # el candidato falso NO se entrega como resultado
