"""Verificadores INDEPENDIENTES del algoritmo que produjo cada resultado (otro algoritmo o una propiedad matemática exacta).
Cada uno devuelve True/False con aritmética exacta (Fraction). No usan NumPy."""
import random
from fractions import Fraction
from .matrix import Matrix


def _matvec(A, v): return [sum((x * y for x, y in zip(r, v)), Fraction(0)) for r in A.rows]


def check_add(a, b, c): return c.shape == a.shape and all(c.rows[i][j] - b.rows[i][j] == a.rows[i][j] for i in range(a.nr) for j in range(a.nc))


def check_sub(a, b, c): return c.shape == a.shape and all(c.rows[i][j] + b.rows[i][j] == a.rows[i][j] for i in range(a.nr) for j in range(a.nc))


def check_mul(a, b, c, seed=11, trials=6):
    """Freivalds exacto: (A·B)·v = A·(B·v) para vectores racionales aleatorios, más dimensiones. Otro orden de operaciones."""
    if c.shape != (a.nr, b.nc): return False
    rnd = random.Random(seed)
    for _ in range(trials):
        v = [Fraction(rnd.randint(-9, 9), rnd.randint(1, 5)) for _ in range(b.nc)]
        if _matvec(c, v) != _matvec(a, _matvec(b, v)): return False
    return True


def check_transpose(a, t): return t.shape == (a.nc, a.nr) and all(t.rows[j][i] == a.rows[i][j] for i in range(a.nr) for j in range(a.nc))


# ----- determinante: Bareiss (sin divisiones fraccionarias intermedias) y Laplace (n ≤ 6), distintos de la eliminación principal -----
def det_bareiss(a):
    M = a.tolist(); n = a.nr; sign = 1; prev = Fraction(1)
    for k in range(n - 1):
        if M[k][k] == 0:
            s = next((i for i in range(k + 1, n) if M[i][k] != 0), None)
            if s is None: return Fraction(0)
            M[k], M[s] = M[s], M[k]; sign = -sign
        for i in range(k + 1, n):
            for j in range(k + 1, n):
                M[i][j] = (M[i][j] * M[k][k] - M[i][k] * M[k][j]) / prev
        prev = M[k][k]
    return sign * M[n - 1][n - 1]


def det_laplace(a):
    M = a.tolist()

    def rec(rows, cols):
        if len(rows) == 1: return M[rows[0]][cols[0]]
        tot = Fraction(0)
        for k, c in enumerate(cols):
            e = M[rows[0]][c]
            if e != 0: tot += (-1) ** k * e * rec(rows[1:], cols[:k] + cols[k + 1:])
        return tot
    return rec(list(range(a.nr)), list(range(a.nc)))


def check_det(a, d):
    if det_bareiss(a) != d: return False
    if a.nr <= 6 and det_laplace(a) != d: return False
    from .ops import transpose
    return det_bareiss(transpose(a)) == d                                  # det(Aᵀ) = det(A)


def check_inverse(a, b):
    from .ops import mul
    I = Matrix.identity(a.nr)
    return b.shape == a.shape and mul(a, b) == I and mul(b, a) == I


def check_rank(a, r, pivots_cols, independent_rows, null_basis):
    """rank ≥ r: existe un menor r×r NO nulo (filas independientes × columnas pivote, det por Bareiss);
    rank ≤ r: existen n−r vectores independientes con A·v = 0 (nulidad ≥ n−r)."""
    if r == 0: return all(x == 0 for row in a.rows for x in row)
    if len(pivots_cols) != r or len(independent_rows) != r: return False
    menor = Matrix([[a.rows[i][j] for j in pivots_cols] for i in independent_rows])
    if det_bareiss(menor) == 0: return False
    if len(null_basis) != a.nc - r: return False
    return all(all(x == 0 for x in _matvec(a, v)) for v in null_basis)


def check_solve(a, b, res):
    bv = [r[0] for r in b.rows]
    if res["kind"] == "none":
        y = res["certificate"]
        yA = [sum((y[i] * a.rows[i][j] for i in range(a.nr)), Fraction(0)) for j in range(a.nc)]
        return all(x == 0 for x in yA) and sum((y[i] * bv[i] for i in range(a.nr)), Fraction(0)) != 0      # Farkas: yᵀA = 0, yᵀb ≠ 0
    if _matvec(a, res["particular"]) != bv: return False
    return all(all(x == 0 for x in _matvec(a, v)) for v in res["nullspace"])
