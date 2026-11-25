"""Evaluador aritmético exacto (racionales) sin dependencias externas.

Solo devuelve resultado exacto cuando lo es. Si el resultado exige simbólico
(p. ej. sqrt(2), pi, variables libres) lanza NotImplementedOperation: no se
aproxima en silencio.
"""
from fractions import Fraction
from math import gcd, isqrt, factorial
from .errors import MathDomainError, NotImplementedOperation, LimitExceeded, ParseError

MAX_EXP = 10000
MAX_FACT = 5000


def _int_root(n, k):
    """Raíz k-ésima entera exacta de n>=0, o None."""
    if n < 2:
        return n
    lo, hi = 1, 1 << (n.bit_length() // k + 1)
    while lo < hi:
        mid = (lo + hi) // 2
        if mid ** k < n:
            lo = mid + 1
        else:
            hi = mid
    return lo if lo ** k == n else None


def _pow(a, b):
    if b.denominator == 1:
        e = b.numerator
        if abs(e) > MAX_EXP:
            raise LimitExceeded("Exponente demasiado grande", {"max": MAX_EXP})
        if a == 0 and e < 0:
            raise MathDomainError("División por cero (0 elevado a exponente negativo)")
        if a == 0 and e == 0:
            raise MathDomainError("0^0 indeterminado")
        if abs(e) * max(a.numerator.bit_length(), a.denominator.bit_length()) > 200000:
            raise LimitExceeded("Resultado demasiado grande")
        return a ** e
    if a < 0:
        raise NotImplementedOperation("Potencia fraccionaria de base negativa requiere números complejos")
    p, q = b.numerator, b.denominator
    rn, rd = _int_root(a.numerator, q), _int_root(a.denominator, q)
    if rn is None or rd is None:
        raise NotImplementedOperation("Resultado irracional exacto: requiere motor simbólico (SymPy)",
                                      {"hint": "sympy"})
    return _pow(Fraction(rn, rd), Fraction(p))


def evaluate(node):
    kind = node[0]
    if kind == "num":
        return node[1]
    if kind == "sym":
        raise NotImplementedOperation(f"Variable libre '{node[1]}': requiere motor simbólico", {"hint": "sympy"})
    if kind == "neg":
        return -evaluate(node[1])
    if kind == "fact":
        n = evaluate(node[1])
        if n.denominator != 1 or n < 0:
            raise MathDomainError("El factorial requiere un entero no negativo")
        if n > MAX_FACT:
            raise LimitExceeded("Factorial demasiado grande", {"max": MAX_FACT})
        return Fraction(factorial(int(n)))
    if kind == "bin":
        op, a, b = node[1], evaluate(node[2]), evaluate(node[3])
        if op == "+": return a + b
        if op == "-": return a - b
        if op == "*": return a * b
        if op == "/":
            if b == 0:
                raise MathDomainError("División por cero")
            return a / b
        if op == "^": return _pow(a, b)
    if kind == "call":
        name, args = node[1], [evaluate(x) for x in node[2]]
        return _call(name, args)
    raise ParseError("Nodo desconocido")


def _ints(name, args, n=None):
    if n is not None and len(args) != n:
        raise ParseError(f"{name} requiere {n} argumento(s)")
    for x in args:
        if x.denominator != 1:
            raise MathDomainError(f"{name} requiere enteros")
    return [int(x) for x in args]


def _call(name, args):
    if name == "abs" and len(args) == 1:
        return abs(args[0])
    if name == "sqrt" and len(args) == 1:
        return _pow(args[0], Fraction(1, 2))
    if name == "root" and len(args) == 2:
        return _pow(args[0], 1 / args[1]) if args[1] != 0 else _raise_zero()
    if name == "gcd":
        a = _ints(name, args); g = 0
        for x in a: g = gcd(g, x)
        return Fraction(g)
    if name == "lcm":
        a = _ints(name, args); l = 1
        for x in a: l = l * x // gcd(l, x) if x else 0
        return Fraction(l)
    if name == "mod":
        a, b = _ints(name, args, 2)
        if b == 0: raise MathDomainError("Módulo por cero")
        return Fraction(a % b)
    if name == "floor" and len(args) == 1:
        return Fraction(args[0].numerator // args[0].denominator)
    if name == "ceil" and len(args) == 1:
        return Fraction(-((-args[0].numerator) // args[0].denominator))
    raise NotImplementedOperation(f"Función '{name}' no implementada en el evaluador exacto", {"hint": "sympy"})


def _raise_zero():
    raise MathDomainError("Raíz de índice cero")


def format_fraction(f):
    return str(f.numerator) if f.denominator == 1 else f"{f.numerator}/{f.denominator}"


def to_decimal(f, digits=30):
    """Aproximación decimal truncada con `digits` decimales (se rotula como aproximación)."""
    sign = "-" if f < 0 else ""
    f = abs(f)
    ip, rem = divmod(f.numerator, f.denominator)
    out = []
    for _ in range(digits):
        rem *= 10
        d, rem = divmod(rem, f.denominator)
        out.append(str(d))
        if rem == 0:
            break
    s = "".join(out).rstrip("0")
    return f"{sign}{ip}" + (f".{s}" if s else "")
