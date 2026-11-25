"""Aproximación decimal de precisión arbitraria con mpmath (motor 0.5.0).

Recorre el AST propio del motor (nunca eval/sympify): mismas funciones y el mismo dominio real que `ast_tools.eval_float`.
Se usa solo cuando el usuario pide más de 15 cifras para un resultado no racional (pi, e, funciones trascendentes);
los racionales y radicales cuadráticos ya tienen cifras exactas por aritmética entera.

Comprobación independiente: el valor de mpmath se contrasta con la evaluación en coma flotante de `eval_float`
(algoritmo distinto, biblioteca distinta). Si no coinciden en ~12 cifras, no se entrega la aproximación.
"""
from .ast_tools import eval_float
from .errors import MathDomainError, NotImplementedOperation, ParseError

try:  # mpmath es opcional: sin él, el motor sigue funcionando con ~15 cifras (con aviso)
    import mpmath
except Exception:  # pragma: no cover - depende del entorno
    mpmath = None

MAX_DIGITS = 1000


def available():
    return mpmath is not None


def _ev(n, mp):
    k = n[0]
    if k == "num":
        q = n[1]                                  # Fraction exacta del parser
        return mp.mpf(q.numerator) / q.denominator if hasattr(q, "numerator") else mp.mpf(str(q))
    if k == "sym":
        if n[1] == "pi": return +mp.pi
        if n[1] == "e": return mp.e + 0
        raise NotImplementedOperation(f"Variable '{n[1]}' sin valor")
    if k == "neg": return -_ev(n[1], mp)
    if k == "fact":
        v = _ev(n[1], mp)
        if v != mp.floor(v) or v < 0: raise MathDomainError("Factorial de un número no natural")
        return mp.factorial(v)
    if k == "bin":
        a, b = _ev(n[2], mp), _ev(n[3], mp)
        op = n[1]
        if op == "+": return a + b
        if op == "-": return a - b
        if op == "*": return a * b
        if op == "/":
            if b == 0: raise MathDomainError("División por cero")
            return a / b
        if op == "^":
            if a < 0 and b != mp.floor(b): raise MathDomainError("Resultado complejo")
            if a == 0 and b <= 0: raise MathDomainError("0 elevado a un exponente no positivo")
            return mp.power(a, b)
    if k == "call":
        if len(n[2]) != 1: raise NotImplementedOperation(f"Función '{n[1]}' no soportada")
        x = _ev(n[2][0], mp)
        name = n[1]
        if name in ("ln", "log"):
            if x <= 0: raise MathDomainError("Logaritmo de un número no positivo")
            return mp.log(x)
        if name == "sqrt":
            if x < 0: raise MathDomainError("Raíz cuadrada de un negativo")
            return mp.sqrt(x)
        if name in ("asin", "acos") and abs(x) > 1: raise MathDomainError(f"{name} fuera de [-1, 1]")
        f = {"sin": mp.sin, "cos": mp.cos, "tan": mp.tan, "exp": mp.exp, "abs": abs, "asin": mp.asin, "acos": mp.acos,
             "atan": mp.atan, "sinh": mp.sinh, "cosh": mp.cosh, "tanh": mp.tanh}.get(name)
        if f is None: raise NotImplementedOperation(f"Función '{name}' no soportada")
        return f(x)
    raise ParseError("Nodo desconocido")


def approx(ast, digits):
    """Texto con `digits` cifras significativas, o None si mpmath no está o el contraste independiente no cuadra."""
    if mpmath is None: return None
    digits = max(1, min(int(digits), MAX_DIGITS))
    ctx = mpmath.mp.clone() if hasattr(mpmath.mp, "clone") else mpmath.mp
    old = ctx.dps
    try:
        ctx.dps = digits + 15                     # cifras de guarda
        v = _ev(ast, ctx)
        if not isinstance(v, type(ctx.mpf(0))): v = ctx.mpf(v)
        ref = eval_float(ast, {})                 # contraste independiente (math, doble precisión)
        if ref != 0 and abs(float(v) - ref) > 1e-11 * max(1.0, abs(ref)): return None
        if ref == 0 and abs(float(v)) > 1e-11: return None
        return ctx.nstr(v, digits, strip_zeros=False, min_fixed=-30, max_fixed=60)
    finally:
        ctx.dps = old
