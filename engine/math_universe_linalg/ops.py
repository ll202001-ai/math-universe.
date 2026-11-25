"""Operaciones de álgebra lineal exactas (sobre Q). Algoritmo principal de cada operación; la verificación independiente está en checks.py."""
from fractions import Fraction
from . import _motor
_motor.ensure()
from math_universe_engine import limits                                   # reutilizado: plazo cooperativo
from math_universe_engine.errors import InvalidRequest, MathDomainError   # reutilizado: errores uniformes
from math_universe_engine.solve import rref as _engine_rref               # reutilizado: Gauss-Jordan exacto del motor
from .matrix import Matrix, fr


def _need_same(a, b, what):
    if a.shape != b.shape:
        raise InvalidRequest(f"{what}: las dimensiones deben coincidir ({a.nr}×{a.nc} frente a {b.nr}×{b.nc})")


def add(a, b):
    _need_same(a, b, "Suma"); return Matrix([[x + y for x, y in zip(r, s)] for r, s in zip(a.rows, b.rows)])


def sub(a, b):
    _need_same(a, b, "Resta"); return Matrix([[x - y for x, y in zip(r, s)] for r, s in zip(a.rows, b.rows)])


def mul(a, b):
    if a.nc != b.nr:
        raise InvalidRequest(f"Producto: columnas de A ({a.nc}) deben igualar filas de B ({b.nr})")
    bt = list(zip(*b.rows)); out = []
    for r in a.rows:
        limits.check()
        out.append([sum((x * y for x, y in zip(r, c)), Fraction(0)) for c in bt])
    return Matrix(out)


def transpose(a):
    return Matrix([list(c) for c in zip(*a.rows)])


def rref_raw(rows, ncols_coef):
    """Envoltura de la rref del motor (no se modifica). `rows`: lista de listas de Fraction. Devuelve (R, pivotes)."""
    return _engine_rref([list(r) for r in rows], ncols_coef, [])


def rref(a):
    R, piv = rref_raw(a.tolist(), a.nc)
    return Matrix(R), piv


def rank(a):
    return len(rref_raw(a.tolist(), a.nc)[1])


def det(a):
    """Eliminación gaussiana con Fractions, siguiendo los cambios de signo por permutación."""
    if not a.is_square(): raise InvalidRequest(f"El determinante exige matriz cuadrada (es {a.nr}×{a.nc})")
    M = a.tolist(); n = a.nr; d = Fraction(1)
    for c in range(n):
        limits.check()
        p = next((i for i in range(c, n) if M[i][c] != 0), None)
        if p is None: return Fraction(0)
        if p != c: M[c], M[p] = M[p], M[c]; d = -d
        d *= M[c][c]
        for i in range(c + 1, n):
            if M[i][c] != 0:
                f = M[i][c] / M[c][c]; M[i] = [x - f * y for x, y in zip(M[i], M[c])]
    return d


def inverse(a):
    """Inversa por [A | I] -> rref. Si es singular lanza MathDomainError con un vector no nulo v tal que A·v = 0 (certificado)."""
    if not a.is_square(): raise InvalidRequest(f"La inversa exige matriz cuadrada (es {a.nr}×{a.nc})")
    n = a.nr
    aug = [list(r) + [Fraction(1 if i == j else 0) for j in range(n)] for i, r in enumerate(a.rows)]
    R, piv = rref_raw(aug, n)
    if len(piv) < n:
        cert = _null_vectors(R, piv, n)[0]
        # el certificado de singularidad se COMPRUEBA antes de afirmarlo: A·v = 0 con v ≠ 0
        if not any(cert) or any(sum((x * y for x, y in zip(r, cert)), Fraction(0)) != 0 for r in a.rows):
            from math_universe_engine.errors import VerificationFailed
            raise VerificationFailed("El certificado de singularidad no se cumple", {"unverified_result": "singular"})
        raise MathDomainError("La matriz es singular (determinante 0): no tiene inversa",
                              {"null_vector": [fr(x) for x in cert], "reason": "A·v = 0 con v ≠ 0"})
    return Matrix([r[n:] for r in R[:n]])


def _null_vectors(R, piv, n):
    """Base del núcleo a partir de la RREF (columnas libres)."""
    libres = [c for c in range(n) if c not in piv]; out = []
    for f in libres:
        v = [Fraction(0)] * n; v[f] = Fraction(1)
        for i, c in enumerate(piv): v[c] = -R[i][f]
        out.append(v)
    return out


def solve(a, b):
    """Resuelve A·x = b. Devuelve dict: kind ∈ {unique, infinite, none}, rank, particular, nullspace, certificate (si none)."""
    if b.nc != 1: raise InvalidRequest("El término independiente b debe ser un vector columna (m×1)")
    if a.nr != b.nr: raise InvalidRequest(f"A tiene {a.nr} filas y b tiene {b.nr}: deben coincidir")
    m, n = a.nr, a.nc
    aug = [list(a.rows[i]) + [b.rows[i][0]] + [Fraction(1 if i == j else 0) for j in range(m)] for i in range(m)]
    R, piv = rref_raw(aug, n)
    rk = len(piv)
    for i in range(rk, m):
        if R[i][n] != 0:
            return {"kind": "none", "rank": rk, "certificate": [R[i][n + 1 + j] for j in range(m)]}
    part = [Fraction(0)] * n
    for i, c in enumerate(piv): part[c] = R[i][n]
    null = _null_vectors(R, piv, n)
    return {"kind": "unique" if not null else "infinite", "rank": rk, "particular": part, "nullspace": null, "pivots": piv,
            "free": [c for c in range(n) if c not in piv]}
