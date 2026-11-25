"""Cuerpo Q(√d): números a + b√d con a,b racionales (d entero libre de cuadrados, d≠0,1).
d<0 representa números complejos a + b·i√|d|. Aritmética exacta."""
from fractions import Fraction
from math import isqrt
from .errors import MathDomainError, NotImplementedOperation


def squarefree_split(n):
    """n>0 entero -> (s, d) con n = s²·d, d libre de cuadrados (factorización por división)."""
    from .limits import check
    s, d, p = 1, n, 2
    while p * p <= d:
        check()
        while d % (p * p) == 0:
            d //= p * p; s *= p
        p += 1 if p == 2 else 2
        if p > 3_000_000:
            raise NotImplementedOperation("Número demasiado grande para extraer cuadrados")
    return s, d


class Q:
    __slots__ = ("a", "b", "d")

    def __init__(self, a=0, b=0, d=1):
        self.a, self.b, self.d = Fraction(a), Fraction(b), d
        if self.b == 0:
            self.d = 1

    @staticmethod
    def sqrt_rational(r):
        """√r exacta como Q (r racional, puede ser negativo)."""
        r = Fraction(r)
        if r == 0:
            return Q(0)
        sign = -1 if r < 0 else 1
        n, m = abs(r.numerator), r.denominator
        s, d = squarefree_split(n * m)   # √(n/m) = √(n·m)/m
        d *= sign
        if d == 1:
            return Q(Fraction(s, m))
        return Q(0, Fraction(s, m), d)

    def _d(self, o):
        if self.b != 0 and o.b != 0 and self.d != o.d:
            raise NotImplementedOperation("Mezcla de radicales distintos no soportada")
        return self.d if self.b != 0 else o.d

    def __add__(s, o):
        o = _q(o); return Q(s.a + o.a, s.b + o.b, s._d(o))

    __radd__ = __add__

    def __neg__(s):
        return Q(-s.a, -s.b, s.d)

    def __sub__(s, o):
        return s + (-_q(o))

    def __rsub__(s, o):
        return _q(o) - s

    def __mul__(s, o):
        o = _q(o); d = s._d(o)
        return Q(s.a * o.a + s.b * o.b * d, s.a * o.b + s.b * o.a, d)

    __rmul__ = __mul__

    def inv(s):
        if s.is_zero():
            raise MathDomainError("División por cero")
        if s.b == 0:
            return Q(1 / s.a)
        n = s.a * s.a - s.b * s.b * s.d
        return Q(s.a / n, -s.b / n, s.d)

    def __truediv__(s, o):
        return s * _q(o).inv()

    def __rtruediv__(s, o):
        return _q(o) * s.inv()

    def __pow__(s, n):
        if not isinstance(n, int):
            raise NotImplementedOperation("Exponente no entero")
        if n < 0:
            return s.inv() ** (-n)
        r, base = Q(1), s
        while n:
            if n & 1: r = r * base
            base = base * base; n >>= 1
        return r

    def is_zero(s):
        return s.a == 0 and s.b == 0

    def __eq__(s, o):
        o = _q(o); return s.a == o.a and s.b == o.b and (s.b == 0 or s.d == o.d)

    def __hash__(s):
        return hash((s.a, s.b, s.d))

    def is_real(s):
        return s.b == 0 or s.d > 0

    def to_float(s):
        if s.b == 0: return float(s.a)
        if s.d > 0: return float(s.a) + float(s.b) * (float(s.d) ** 0.5)
        raise MathDomainError("Número complejo")

    def to_complex(s):
        if s.d > 0 or s.b == 0: return complex(s.to_float())
        return complex(float(s.a), float(s.b) * (float(-s.d) ** 0.5))

    def __str__(s):
        def fr(x):
            return str(x.numerator) if x.denominator == 1 else f"{x.numerator}/{x.denominator}"
        if s.b == 0:
            return fr(s.a)
        rad = f"sqrt({s.d})" if s.d > 0 else (f"sqrt({-s.d})*i" if s.d != -1 else "i")
        mag = abs(s.b)
        bt = rad if mag == 1 else (f"{fr(mag)}*{rad}" if mag.denominator == 1 else f"({fr(mag)})*{rad}")
        if s.a == 0:
            return ("-" if s.b < 0 else "") + bt
        return f"{fr(s.a)} {'-' if s.b < 0 else '+'} {bt}"

    __repr__ = __str__


def _q(o):
    return o if isinstance(o, Q) else Q(o)


def q_to_decimal(q, sig):
    """Valor REAL a + b·√d con `sig` cifras significativas, correctamente redondeado, con aritmética entera exacta
    (sin floats ni mpmath). Devuelve str decimal plano. Requiere d > 0 (real)."""
    import decimal, math
    from math import isqrt
    if q.b == 0:
        a = q.a
        num, den = a.numerator, a.denominator
    elif q.d < 0:
        raise ValueError("valor complejo")
    else:
        num = den = None
    est = q.to_float()
    if est == 0 and q.b == 0:
        return "0"
    e10 = math.floor(math.log10(abs(est))) if est != 0 else 0

    def scaled(guard):
        P = max(0, sig - e10 + guard)
        S = 10 ** P
        if q.b == 0:
            N = (num * S) // den
        else:
            r = isqrt(q.d * S * S)                       # floor(√d · S)
            # a·S + b·√d·S con error acotado por |b|+1 unidades de 10^-P
            N = (q.a.numerator * S) // q.a.denominator + (q.b.numerator * r) // q.b.denominator
        return N, P

    outs = []
    for guard in (12, 30):
        N, P = scaled(guard)
        with decimal.localcontext() as ctx:
            ctx.prec = sig
            ctx.rounding = decimal.ROUND_HALF_EVEN
            outs.append(+decimal.Decimal(N).scaleb(-P))
    d = outs[0]
    if outs[0] != outs[1]:                       # frontera de redondeo dudosa: se recalcula con más cifras de guarda
        N, P = scaled(60)
        with decimal.localcontext() as ctx:
            ctx.prec = sig; ctx.rounding = decimal.ROUND_HALF_EVEN
            d = +decimal.Decimal(N).scaleb(-P)
    return format(d, "f")                        # se conservan los ceros finales: son cifras significativas
