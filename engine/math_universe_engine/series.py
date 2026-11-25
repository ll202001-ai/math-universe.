"""Series de Laurent truncadas con coeficientes racionales exactos (para límites)."""
from fractions import Fraction
from math import factorial
from . import limits
from .errors import NotImplementedOperation, MathDomainError

INF = 10 ** 9


class Ser:
    """Σ c[k] t^k + O(t^O)."""
    __slots__ = ("c", "O")

    def __init__(self, c, O):
        self.c = {k: v for k, v in c.items() if v != 0 and k < O}; self.O = O

    def val(self):
        return min(self.c) if self.c else None

    def __add__(s, o): return Ser({k: s.c.get(k, 0) + o.c.get(k, 0) for k in set(s.c) | set(o.c)}, min(s.O, o.O))
    def __neg__(s): return Ser({k: -v for k, v in s.c.items()}, s.O)
    def __sub__(s, o): return s + (-o)

    def _vlow(s): return s.val() if s.c else s.O

    def __mul__(s, o):
        limits.check()
        O = min(s._vlow() + o.O if o.O < INF else INF, o._vlow() + s.O if s.O < INF else INF)
        if not s.c or not o.c:
            return Ser({}, O if O < INF else INF) if (s.O < INF or o.O < INF) else Ser({}, INF)
        r = {}
        for k1, v1 in s.c.items():
            for k2, v2 in o.c.items():
                if k1 + k2 < O: r[k1 + k2] = r.get(k1 + k2, 0) + v1 * v2
        return Ser(r, O)

    def inv(s, M=64):
        if not s.c: raise MathDomainError("División por serie nula (no se puede decidir con la precisión actual)")
        v = s.val(); m = min(s.O - v, max(1, M + v))
        a = [s.c.get(v + i, Fraction(0)) for i in range(m)]
        b = [Fraction(0)] * m; b[0] = 1 / a[0]
        for k in range(1, m):
            limits.check()
            b[k] = -b[0] * sum(a[j] * b[k - j] for j in range(1, k + 1) if j < m)
        return Ser({-v + i: b[i] for i in range(m)}, -v + m)

    def pow(s, n, M=64):
        if n < 0: return trunc(s.inv(M), M).pow(-n, M)
        r = Ser({0: Fraction(1)}, INF); b = s
        while n:
            if n & 1: r = r * b
            n >>= 1
            if n: b = b * b
        return r


def const(c): return Ser({0: Fraction(c)}, INF)


def trunc(s, M):
    return Ser({k: v for k, v in s.c.items() if k < M}, min(s.O, M))


def _series_sum(s, coeff, M):
    """Σ coeff(k) s^k para s con valuación >0, hasta orden M."""
    v = s.val()
    if v is None: return const(coeff(0))
    if v <= 0: raise NotImplementedOperation("Argumento sin término constante nulo: función no desarrollable aquí")
    total = const(coeff(0)); p = const(1); k = 0
    while True:
        k += 1
        if k * v >= M: break
        p = trunc(p * s, M)
        total = total + Ser({kk: vv * coeff(k) for kk, vv in p.c.items()}, p.O)
    return trunc(total, M)


def apply(f, s, M):
    """Función elemental sobre una serie. s debe tener término constante 0 (salvo ln, sqrt)."""
    c0 = s.c.get(0, Fraction(0))
    if f in ("ln", "sqrt"):
        if c0 == 0 and s.c: raise NotImplementedOperation(f"{f} de una serie con término constante 0: no desarrollable")
        if f == "ln":
            if c0 != 1: raise NotImplementedOperation("ln solo con término constante 1")
            u = s - const(1); v = u.val()
            if v is None: return const(0)
            if v <= 0: raise NotImplementedOperation("ln: argumento no cercano a 1")
            return _series_sum_from1(u, lambda k: Fraction((-1) ** (k + 1), k), M)
        from .arith import _int_root
        if c0 <= 0: raise NotImplementedOperation("sqrt de término constante no positivo")
        rn, rd = _int_root(c0.numerator, 2), _int_root(c0.denominator, 2)
        if rn is None or rd is None: raise NotImplementedOperation("sqrt de racional no cuadrado perfecto")
        u = Ser({k: v / c0 for k, v in s.c.items() if k != 0}, s.O)
        def binom(k):
            r = Fraction(1)
            for j in range(k): r *= (Fraction(1, 2) - j) / (j + 1)
            return r
        return _series_sum(u, binom, M) * const(Fraction(rn, rd))
    if c0 != 0 and s.c: raise NotImplementedOperation(f"{f}: argumento con término constante no nulo")
    if f == "exp": return _series_sum(s, lambda k: Fraction(1, factorial(k)), M)
    if f == "sin": return _series_sum_odd(s, M, +1, False)
    if f == "cos": return _series_sum_odd(s, M, +1, True)
    if f == "sinh": return _series_sum_hyp(s, M, False)
    if f == "cosh": return _series_sum_hyp(s, M, True)
    if f == "atan": return _series_sum_atan(s, M)
    if f == "tan": return trunc(apply("sin", s, M) * apply("cos", s, M).inv(M), M)
    if f == "tanh": return trunc(apply("sinh", s, M) * apply("cosh", s, M).inv(M), M)
    raise NotImplementedOperation(f"Función '{f}' sin desarrollo en serie implementado")


def _series_sum_from1(u, coeff, M):
    v = u.val(); total = Ser({}, M); p = const(1); k = 0
    while True:
        k += 1
        if k * v >= M: break
        p = trunc(p * u, M)
        total = total + Ser({kk: vv * coeff(k) for kk, vv in p.c.items()}, p.O)
    return trunc(total, M)


def _series_sum_odd(s, M, sign, even):
    def coeff(k):
        if even: return Fraction((-1) ** (k // 2), factorial(k)) if k % 2 == 0 else Fraction(0)
        return Fraction((-1) ** (k // 2), factorial(k)) if k % 2 == 1 else Fraction(0)
    return _series_sum(s, coeff, M)


def _series_sum_hyp(s, M, even):
    return _series_sum(s, lambda k: Fraction(1, factorial(k)) if (k % 2 == 0) == even else Fraction(0), M)


def _series_sum_atan(s, M):
    return _series_sum(s, lambda k: Fraction((-1) ** (k // 2), k) if k % 2 == 1 else Fraction(0), M)
