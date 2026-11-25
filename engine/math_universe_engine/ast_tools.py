"""Herramientas sobre el AST: normalización, impresión re-analizable, evaluación independiente,
derivación simbólica y sustitución."""
import math
from fractions import Fraction
from .errors import MathDomainError, NotImplementedOperation, ParseError
from .qsqrt import Q
from . import arith, limits

CONSTANTS = {"pi", "e"}
FUNCS = {"sin", "cos", "tan", "exp", "ln", "log", "sqrt", "abs", "asin", "acos", "atan", "sinh", "cosh", "tanh"}


def num(x): return ("num", Fraction(x))
ZERO, ONE = num(0), num(1)


def mk_neg(a):
    return num(-a[1]) if a[0] == "num" else (a[1] if a[0] == "neg" else ("neg", a))


def mk_add(a, b):
    if a == ZERO: return b
    if b == ZERO: return a
    if a[0] == "num" and b[0] == "num": return num(a[1] + b[1])
    return ("bin", "+", a, b)


def mk_sub(a, b): return mk_add(a, mk_neg(b))


def mk_mul(a, b):
    if a == ZERO or b == ZERO: return ZERO
    if a == ONE: return b
    if b == ONE: return a
    if a[0] == "num" and b[0] == "num": return num(a[1] * b[1])
    return ("bin", "*", a, b)


def mk_div(a, b):
    if a == ZERO: return ZERO
    if b == ONE: return a
    return ("bin", "/", a, b)


def mk_pow(a, b):
    if b == ONE: return a
    if b == ZERO: return ONE
    return ("bin", "^", a, b)


def normalize(n):
    """e^u -> exp(u); log -> ln; sin/cos con nombres en minúscula."""
    k = n[0]
    if k in ("num", "sym"): return n
    if k == "neg": return ("neg", normalize(n[1]))
    if k == "fact": return ("fact", normalize(n[1]))
    if k == "bin":
        a, b = normalize(n[2]), normalize(n[3])
        if n[1] == "^" and a == ("sym", "e"): return ("call", "exp", [b])
        return ("bin", n[1], a, b)
    name = "ln" if n[1] == "log" else n[1]
    return ("call", name, [normalize(x) for x in n[2]])


def free_symbols(n, acc=None):
    acc = set() if acc is None else acc
    k = n[0]
    if k == "sym":
        if n[1] not in CONSTANTS: acc.add(n[1])
    elif k in ("neg", "fact"): free_symbols(n[1], acc)
    elif k == "bin": free_symbols(n[2], acc); free_symbols(n[3], acc)
    elif k == "call":
        for a in n[2]: free_symbols(a, acc)
    return acc


def contains(n, v): return v in free_symbols(n)


def to_str(n, prec=0):
    k = n[0]
    if k == "num":
        f = n[1]
        s = str(f.numerator) if f.denominator == 1 else f"{f.numerator}/{f.denominator}"
        return f"({s})" if (f < 0 or f.denominator != 1) and prec > 0 else s
    if k == "sym": return n[1]
    if k == "neg":
        s = "-" + to_str(n[1], 25); return f"({s})" if prec > 10 else s
    if k == "fact": return to_str(n[1], 40) + "!"
    if k == "call": return f"{n[1]}({', '.join(to_str(a) for a in n[2])})"
    op = n[1]; p = {"+": 10, "-": 10, "*": 20, "/": 20, "^": 30}[op]
    l = to_str(n[2], p if op != "^" else 31)
    r = to_str(n[3], p + 1 if op != "^" else 30)
    s = f"{l} {op} {r}" if op in "+-" else f"{l}{op}{r}" if op == "^" else f"{l}{op}{r}"
    return f"({s})" if p < prec or (p == prec and op in "+-/" and False) else s


def subs(n, v, rep):
    k = n[0]
    if k == "sym": return rep if n[1] == v else n
    if k == "num": return n
    if k in ("neg", "fact"): return (k, subs(n[1], v, rep))
    if k == "bin": return ("bin", n[1], subs(n[2], v, rep), subs(n[3], v, rep))
    return ("call", n[1], [subs(a, v, rep) for a in n[2]])


# ---------------- evaluación independiente ----------------
def eval_q(n, env):
    """Evalúa en Q(√d) exacto. env: {nombre: Fraction|Q}. Solo operaciones racionales + sqrt/abs de racionales."""
    k = n[0]
    if k == "num": return Q(n[1])
    if k == "sym":
        if n[1] not in env: raise NotImplementedOperation(f"Variable '{n[1]}' sin valor")
        return env[n[1]] if isinstance(env[n[1]], Q) else Q(env[n[1]])
    if k == "neg": return -eval_q(n[1], env)
    if k == "fact": return Q(arith.evaluate(("fact", ("num", _as_frac(eval_q(n[1], env))))))
    if k == "bin":
        a, b = eval_q(n[2], env), eval_q(n[3], env)
        op = n[1]
        if op == "+": return a + b
        if op == "-": return a - b
        if op == "*": return a * b
        if op == "/":
            if b.is_zero(): raise MathDomainError("División por cero")
            return a / b
        if op == "^":
            if b.b != 0 or b.a.denominator != 1:
                if b.b == 0 and a.b == 0:
                    return Q(arith._pow(a.a, b.a))
                raise NotImplementedOperation("Potencia no entera de número con radicales")
            if a.is_zero() and b.a <= 0: raise MathDomainError("0 con exponente no positivo")
            if abs(b.a) > 10000: raise NotImplementedOperation("Exponente muy grande")
            return a ** int(b.a)
    if k == "call":
        args = [eval_q(x, env) for x in n[2]]
        if n[1] == "sqrt" and len(args) == 1 and args[0].b == 0:
            return Q.sqrt_rational(args[0].a) if args[0].a >= 0 else Q.sqrt_rational(args[0].a)
        if n[1] == "abs" and len(args) == 1 and args[0].b == 0:
            return Q(abs(args[0].a))
    raise NotImplementedOperation("Función no evaluable exactamente")


def _as_frac(q):
    if q.b != 0: raise MathDomainError("Se requiere racional")
    return q.a


def eval_float(n, env):
    """Evaluación numérica en coma flotante (reales). Lanza ValueError/MathDomainError en puntos inválidos."""
    k = n[0]
    if k == "num": return float(n[1])
    if k == "sym":
        if n[1] == "pi": return math.pi
        if n[1] == "e": return math.e
        if n[1] not in env: raise NotImplementedOperation(f"Variable '{n[1]}' sin valor")
        return float(env[n[1]])
    if k == "neg": return -eval_float(n[1], env)
    if k == "fact": return float(math.factorial(int(eval_float(n[1], env))))
    if k == "bin":
        a, b = eval_float(n[2], env), eval_float(n[3], env)
        op = n[1]
        if op == "+": return a + b
        if op == "-": return a - b
        if op == "*": return a * b
        if op == "/":
            if b == 0: raise MathDomainError("División por cero")
            return a / b
        if op == "^":
            r = a ** b
            if isinstance(r, complex): raise MathDomainError("Resultado complejo")
            return r
    if k == "call":
        a = [eval_float(x, env) for x in n[2]]
        f = {"sin": math.sin, "cos": math.cos, "tan": math.tan, "exp": math.exp, "ln": math.log, "log": math.log,
             "sqrt": math.sqrt, "abs": abs, "asin": math.asin, "acos": math.acos, "atan": math.atan,
             "sinh": math.sinh, "cosh": math.cosh, "tanh": math.tanh}.get(n[1])
        if f is None or len(a) != 1: raise NotImplementedOperation(f"Función '{n[1]}' no soportada")
        return f(a[0])
    raise ParseError("Nodo desconocido")


# ---------------- derivación simbólica ----------------
def const_value(n):
    """Valor racional si n es una constante racional evaluable, o None."""
    try:
        return arith.evaluate(n)
    except Exception:
        return None


def deriv(n, v):
    limits.check()
    if not contains(n, v): return ZERO
    k = n[0]
    if k == "sym": return ONE
    if k == "neg": return mk_neg(deriv(n[1], v))
    if k == "bin":
        op, a, b = n[1], n[2], n[3]
        da, db = deriv(a, v), deriv(b, v)
        if op == "+": return mk_add(da, db)
        if op == "-": return mk_sub(da, db)
        if op == "*": return mk_add(mk_mul(da, b), mk_mul(a, db))
        if op == "/": return mk_div(mk_sub(mk_mul(da, b), mk_mul(a, db)), mk_pow(b, num(2)))
        if op == "^":
            if not contains(b, v):
                c = const_value(b)
                ex = mk_sub(b, ONE) if c is None else num(c - 1)
                return mk_mul(mk_mul(b, mk_pow(a, ex)), da)
            if not contains(a, v):
                return mk_mul(mk_mul(n, ("call", "ln", [a])), db)
            return mk_mul(n, mk_add(mk_mul(db, ("call", "ln", [a])), mk_div(mk_mul(b, da), a)))
    if k == "call":
        f, u = n[1], n[2][0]; du = deriv(u, v)
        if f == "sin": d = ("call", "cos", [u])
        elif f == "cos": d = mk_neg(("call", "sin", [u]))
        elif f == "tan": d = mk_add(ONE, mk_pow(("call", "tan", [u]), num(2)))
        elif f == "exp": d = n
        elif f == "ln": return mk_div(du, u)
        elif f == "sqrt": return mk_div(du, mk_mul(num(2), n))
        elif f == "abs": d = mk_div(u, n)
        elif f == "asin": d = mk_div(ONE, ("call", "sqrt", [mk_sub(ONE, mk_pow(u, num(2)))]))
        elif f == "acos": d = mk_neg(mk_div(ONE, ("call", "sqrt", [mk_sub(ONE, mk_pow(u, num(2)))])))
        elif f == "atan": d = mk_div(ONE, mk_add(ONE, mk_pow(u, num(2))))
        elif f == "sinh": d = ("call", "cosh", [u])
        elif f == "cosh": d = ("call", "sinh", [u])
        elif f == "tanh": d = mk_sub(ONE, mk_pow(n, num(2)))
        else: raise NotImplementedOperation(f"Derivada de '{f}' no implementada")
        return mk_mul(d, du)
    raise NotImplementedOperation("Derivada no soportada para este nodo")
