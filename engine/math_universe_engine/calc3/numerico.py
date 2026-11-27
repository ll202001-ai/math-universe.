"""Cuadratura independiente (tanh-sinh anidada) para verificar y para integrales sin primitiva elemental."""
import math
from fractions import Fraction
from ..ast_tools import normalize, free_symbols
from ..parser import parse

_SAFE = {"sin": "_m.sin", "cos": "_m.cos", "tan": "_m.tan", "exp": "_m.exp", "ln": "_m.log", "log": "_m.log", "sqrt": "_m.sqrt",
         "abs": "abs", "asin": "_m.asin", "acos": "_m.acos", "atan": "_m.atan", "sinh": "_m.sinh", "cosh": "_m.cosh",
         "tanh": "_m.tanh", "sen": "_m.sin"}


def _src(n):
    k = n[0]
    if k == "num":
        f = n[1]; return repr(float(f)) if f.denominator != 1 else repr(float(f.numerator))
    if k == "sym":
        if n[1] == "pi": return "_m.pi"
        if n[1] == "e": return "_m.e"
        return n[1]
    if k == "neg": return f"(-{_src(n[1])})"
    if k == "bin":
        a, b = _src(n[2]), _src(n[3])
        if n[1] == "^":
            return f"_pw({a},{b})"
        return f"({a}{n[1]}{b})"
    if k == "call":
        f = _SAFE.get(n[1])
        if f is None or len(n[2]) != 1: raise ValueError("función no soportada: " + n[1])
        return f"{f}({_src(n[2][0])})"
    raise ValueError("nodo")


def _pw(a, b):
    if a < 0 and b != int(b): raise ValueError("raíz de negativo")
    if a == 0 and b < 0: raise ZeroDivisionError
    return a ** b


def compile_ast(ast, names):
    code = f"lambda {','.join(names)}: {_src(ast)}"
    return eval(code, {"_m": math, "_pw": _pw, "abs": abs})


def compile_text(s, names):
    return compile_ast(normalize(parse(s)), names)


_NODES = {}


def _nodes(h):
    if h in _NODES: return _NODES[h]
    out = []; k = 0
    tmax = 3.3 if h >= 1 / 16 else 3.5
    n = int(tmax / h)
    for i in range(-n, n + 1):
        t = i * h; u = math.pi / 2 * math.sinh(t)
        w = (math.pi / 2) * math.cosh(t) / math.cosh(u) ** 2
        out.append((u, w * h))
    _NODES[h] = out
    return out


def _ts(f, a, b, h):
    if a == b: return 0.0
    s = 0.0; L = b - a
    for u, w in _nodes(h):
        if u < 0: x = a + L / (1 + math.exp(-2 * u))
        else: x = b - L / (1 + math.exp(2 * u))
        if x <= min(a, b) and a < b or x >= max(a, b) and b < a:
            pass
        try:
            v = f(x)
        except (ValueError, ZeroDivisionError, OverflowError):
            continue
        if isinstance(v, complex) or v != v or abs(v) == float("inf"): continue
        s += v * w * 0.5
    return s * L


def integrate_nested(f, bounds, h=0.125):
    """f(v0, v1, ..) ; bounds: lista de (lo, hi) del NIVEL MÁS INTERNO al más externo, cada uno función de las
    variables externas (en el orden: más externa primero). Devuelve ∫…∫ f.
    Ej. ∫_0^1 ∫_0^x f(x,y) dy dx → f(x,y), bounds=[(lambda x:0, lambda x:x), (0,1)] (interna primero)."""
    n = len(bounds)

    def rec(level, outer):             # level: índice en bounds desde la más externa
        idx = n - 1 - level
        lo, hi = bounds[idx]
        a = lo(*outer) if callable(lo) else lo
        b = hi(*outer) if callable(hi) else hi
        if level == n - 1:
            return _ts(lambda t: f(*(outer + (t,))), a, b, h)
        return _ts(lambda t: rec(level + 1, outer + (t,)), a, b, h)
    return rec(0, ())


def integral(f, bounds):
    """Con comprobación de convergencia: h=1/4 contra h=1/8 (y h=1/16 si hace falta y es barato)."""
    d = len(bounds)
    r1 = integrate_nested(f, bounds, 0.25)
    r2 = integrate_nested(f, bounds, 0.125)
    err = abs(r1 - r2)
    if err > 1e-9 * (1 + abs(r2)) and d <= 2:
        r3 = integrate_nested(f, bounds, 0.0625)
        return r3, abs(r3 - r2)
    return r2, err
