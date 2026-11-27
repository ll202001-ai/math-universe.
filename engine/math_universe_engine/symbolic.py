"""Backend simbólico (SymPy). ESTADO: implementado, SIN PROBAR en este entorno
(SymPy no está instalado aquí). Se convierte el AST propio a SymPy: nunca sympify/eval.
"""
from fractions import Fraction
from .errors import DependencyMissing, NotImplementedOperation, ParseError, NotSolved

try:
    import sympy as sp
except ImportError:  # pragma: no cover
    sp = None


SYMBOLIC_OPS = {"simplify", "expand", "factor", "differentiate", "integrate", "evaluate"}


def available():
    """SymPy instalado Y no deshabilitado (MATH_UNIVERSE_DISABLE_SYMPY=1 fuerza el motor propio puro: lo usan las pruebas
    del motor propio para que sus resultados no dependan de qué paquetes haya instalados)."""
    import os
    if os.environ.get("MATH_UNIVERSE_DISABLE_SYMPY") == "1": return False
    return sp is not None


def from_sympy_text(t):
    """Texto de SymPy -> sintaxis del motor (Abs->abs, log->ln, E->e, I->i, ** se acepta tal cual)."""
    import re
    t = re.sub(r"\bAbs\(", "abs(", t)
    t = re.sub(r"\blog\(", "ln(", t)
    t = re.sub(r"\bE\b", "e", t)
    t = re.sub(r"\bI\b", "i", t)
    t = re.sub(r"\bceiling\(", "ceil(", t)
    return t.replace("**", "^")


def _need():
    if sp is None:
        raise DependencyMissing("SymPy no está disponible en este entorno",
                                {"package": "sympy"})


_FUNCS = {}


def _funcs():
    if not _FUNCS:
        _FUNCS.update({"sin": sp.sin, "cos": sp.cos, "tan": sp.tan, "exp": sp.exp,
                       "ln": sp.log, "log": sp.log, "sqrt": sp.sqrt, "abs": sp.Abs,
                       "asin": sp.asin, "acos": sp.acos, "atan": sp.atan,
                       "sinh": sp.sinh, "cosh": sp.cosh, "tanh": sp.tanh,
                       # 0.7.0
                       "sec": sp.sec, "csc": sp.csc, "cot": sp.cot, "asinh": sp.asinh, "acosh": sp.acosh,
                       "atanh": sp.atanh, "cbrt": lambda v: sp.real_root(v, 3), "gamma": sp.gamma, "erf": sp.erf,
                       "erfc": sp.erfc, "beta": sp.beta, "zeta": sp.zeta, "besselj": sp.besselj,
                       "floor": sp.floor, "ceil": sp.ceiling, "root": lambda v, n: sp.real_root(v, n) if n.is_odd else sp.root(v, n)})
    return _FUNCS


def to_sympy(node):
    _need()
    k = node[0]
    if k == "num":
        f = node[1]
        return sp.Rational(f.numerator, f.denominator)
    if k == "sym":
        n = node[1]
        if n == "pi": return sp.pi
        if n == "e": return sp.E
        if n == "i": return sp.I
        return sp.Symbol(n)
    if k == "neg": return -to_sympy(node[1])
    if k == "fact": return sp.factorial(to_sympy(node[1]))
    if k == "bin":
        a, b = to_sympy(node[2]), to_sympy(node[3])
        return {"+": a + b, "-": a - b, "*": a * b, "/": a / b, "^": a ** b}[node[1]]
    if k == "call":
        if node[1] in ("log", "ln") and len(node[2]) == 2:
            return sp.log(to_sympy(node[2][0]), to_sympy(node[2][1]))
        fn = _funcs().get(node[1])
        if fn is None:
            raise NotImplementedOperation(f"Función '{node[1]}' no reconocida")
        return fn(*[to_sympy(x) for x in node[2]])
    raise ParseError("Nodo desconocido")


def _var(expr, variables):
    if variables:
        return sp.Symbol(variables[0])
    free = sorted(expr.free_symbols, key=lambda s: s.name)
    if len(free) == 1:
        return free[0]
    from .errors import InvalidRequest
    raise InvalidRequest("Indique la variable (hay cero o varias variables libres)",
                         {"free": [s.name for s in free]})


def run(operation, ast, variables):
    _need()
    expr = to_sympy(ast)
    if operation == "evaluate":
        r = sp.simplify(expr)
        if r.has(sp.zoo, sp.nan) or r in (sp.oo, -sp.oo):
            from .errors import MathDomainError
            raise MathDomainError("La expresión no está definida (división por cero o argumento fuera del dominio)")
        return from_sympy_text(str(r))
    if operation == "simplify": return from_sympy_text(str(sp.simplify(expr)))
    if operation == "expand": return from_sympy_text(str(sp.expand(expr)))
    if operation == "factor": return from_sympy_text(str(sp.factor(expr)))
    if operation == "differentiate": return from_sympy_text(str(sp.diff(expr, _var(expr, variables))))
    if operation == "integrate":
        res = sp.integrate(expr, _var(expr, variables))
        if res.has(sp.Integral):
            raise NotSolved("SymPy no encontró una primitiva (no implica que no exista)")
        return from_sympy_text(str(res)) + " + C"
    raise NotImplementedOperation(f"Operación '{operation}' sin backend simbólico")
