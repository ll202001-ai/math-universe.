"""Funciones racionales exactas con átomos (sin(x), sqrt(2), pi, ...), conversión desde AST,
cancelación, impresión re-analizable y recopilación de condiciones de dominio."""
from fractions import Fraction
from . import arith, limits
from .ast_tools import const_value, to_str, CONSTANTS
from .errors import MathDomainError, NotImplementedOperation, LimitExceeded
from .poly import Poly, u_factor, u_to_poly


class RF:
    __slots__ = ("n", "d")

    def __init__(self, n, d=None):
        self.n = n if isinstance(n, Poly) else Poly.const(n)
        self.d = Poly.const(1) if d is None else (d if isinstance(d, Poly) else Poly.const(d))

    def is_zero(s): return s.n.is_zero()
    def __add__(s, o): return RF(s.n * o.d + o.n * s.d, s.d * o.d)
    def __sub__(s, o): return RF(s.n * o.d - o.n * s.d, s.d * o.d)
    def __mul__(s, o): return RF(s.n * o.n, s.d * o.d)
    def __neg__(s): return RF(-s.n, s.d)
    def inv(s):
        if s.n.is_zero(): raise MathDomainError("División por cero")
        return RF(s.d, s.n)

    def __truediv__(s, o): return s * o.inv()

    def pow(s, k):
        if k >= 0: return RF(s.n ** k, s.d ** k)
        return s.inv().pow(-k)

    def cancel(s, warnings=None):
        s = RF(reduce_sqrt_atoms(s.n), reduce_sqrt_atoms(s.d))
        if s.n.is_zero(): return RF(Poly(), Poly.const(1))
        cn, mn, rn = s.n.content_and_monomial()
        cd, md, rd = s.d.content_and_monomial()
        # monomio común
        dn, dd = dict(mn), dict(md)
        common = {v: min(e, dd[v]) for v, e in dn.items() if v in dd}
        mn2 = dict(dn); md2 = dict(dd)
        for v, e in common.items():
            mn2[v] -= e; md2[v] -= e
            if mn2[v] == 0: del mn2[v]
            if md2[v] == 0: del md2[v]
        const = cn / cd
        # división exacta entre las partes primitivas
        q = rn.exact_div(rd) if rd.degree() > 0 else None
        if q is not None:
            rn, rd = q, Poly.const(1)
        elif rn.degree() > 0:
            q2 = rd.exact_div(rn)
            if q2 is not None: rn, rd = Poly.const(1), q2
        vs = set(rn.vars()) | set(rd.vars())
        if len(vs) == 1 and rn.degree() > 0 and rd.degree() > 0:
            from .poly import u_gcd, u_divmod
            v = next(iter(vs)); a, b = rn.to_upoly(v), rd.to_upoly(v)
            g = u_gcd(a, b)
            if len(g) > 1:
                a = u_divmod(a, g)[0]; b = u_divmod(b, g)[0]
                rn, rd = u_to_poly(a, v), u_to_poly(b, v)
                c2, m2, rn2 = rn.content_and_monomial(); c3, m3, rd2 = rd.content_and_monomial()
                const = const * c2 / c3
                rn = rn2 * Poly({m2: Fraction(1)}); rd = rd2 * Poly({m3: Fraction(1)})
        elif len(vs) > 1 and rn.degree() > 0 and rd.degree() > 0 and warnings is not None:
            warnings.append("Posible factor común multivariante no cancelado (solo se cancelan monomios, contenido y divisores exactos)")
        num = Poly({tuple(sorted(mn2.items())): const}) * rn
        den = Poly({tuple(sorted(md2.items())): Fraction(1)}) * rd
        return RF(num, den)


import re as _re
_SQRT_ATOM = _re.compile(r"^sqrt\((\d+)\)$")


def reduce_sqrt_atoms(p):
    """sqrt(d)^e -> d^(e//2)·sqrt(d)^(e%2) (d entero libre de cuadrados): identidad válida sin restricciones."""
    out = {}
    for m, c in p.t.items():
        newm, coef = [], c
        for v, e in m:
            mt = _SQRT_ATOM.match(v)
            if mt and e >= 2:
                coef = coef * Fraction(int(mt.group(1))) ** (e // 2)
                if e % 2: newm.append((v, 1))
            else:
                newm.append((v, e))
        key = tuple(sorted(newm))
        out[key] = out.get(key, 0) + coef
    return Poly(out)


def rf_str(r):
    if r.n.is_const() and not r.d.is_const() and r.n.const_value().denominator != 1:
        q = r.n.const_value()                      # (p/q)/D  ->  p/(q·D): evita el "1/2/sqrt(x)" ambiguo
        r = RF(Poly.const(q.numerator), r.d * Poly.const(q.denominator))
    if r.d == Poly.const(1) or str(r.n) == "0": return str(r.n)      # 0/(x-2) se imprime 0 (la condición x≠2 queda en `conditions`)
    ns = str(r.n)
    if len(r.n.t) > 1: ns = f"({ns})"
    ds = str(r.d)
    simple = len(r.d.t) == 1 and (lambda m, c: c == 1 and len(m) == 1)(*next(iter(r.d.t.items())))
    if not simple and not (r.d.is_const()): ds = f"({ds})"
    elif r.d.is_const() and "/" in ds: ds = f"({ds})"
    return f"{ns}/{ds}"


class Ctx:
    def __init__(self, assumptions=None):
        self.conds = []        # polinomios que deben ser ≠ 0
        self.ineqs = []        # condiciones de desigualdad en texto (ln, sqrt)
        self.warnings = []
        self.assumptions = assumptions or {}


def _atom(name): return RF(Poly.var(name))


def _num_rf(c): return RF(Poly.const(c))


def to_rf(n, ctx):
    limits.check()
    k = n[0]
    if k == "num": return _num_rf(n[1])
    if k == "sym":
        return _atom(n[1])
    if k == "neg": return -to_rf(n[1], ctx)
    if k == "fact":
        return _num_rf(arith.evaluate(n))
    if k == "bin":
        op = n[1]
        if op == "^":
            return _pow(n, ctx)
        a, b = to_rf(n[2], ctx), to_rf(n[3], ctx)
        if op == "+": return a + b
        if op == "-": return a - b
        if op == "*": return a * b
        if op == "/":
            if b.is_zero(): raise MathDomainError("División por cero")
            if not b.n.is_const(): ctx.conds.append(b.n)
            return a / b
    if k == "call":
        return _call(n, ctx)
    raise NotImplementedOperation("Nodo no soportado")


def _pow(n, ctx):
    base_n, ex_n = n[2], n[3]
    c = const_value(ex_n)
    if (c is not None and c.denominator == 1 and c % 2 == 0 and c != 0 and base_n[0] == "call"
            and base_n[1] == "sqrt" and len(base_n[2]) == 1):
        # sqrt(u)^(2k) = u^k (con la condición u >= 0 que impone sqrt)
        _call(base_n, ctx)
        return to_rf(base_n[2][0], ctx).pow(int(c) // 2) if int(c) > 0 else _pow(("bin", "^", base_n[2][0], ("num", c / 2)), ctx)
    if c is not None and c.denominator == 1:
        b = to_rf(base_n, ctx)
        k = int(c)
        if abs(k) > limits.MAX_POW: raise LimitExceeded("Exponente demasiado grande", {"max": limits.MAX_POW})
        if k < 0:
            if b.is_zero(): raise MathDomainError("División por cero")
            if not b.n.is_const(): ctx.conds.append(b.n)
        if k == 0:
            if b.is_zero(): raise MathDomainError("0^0 indeterminado")
            if not b.n.is_const(): ctx.conds.append(b.n)
            return _num_rf(1)
        return b.pow(k)
    b = to_rf(base_n, ctx)
    if c is not None:  # exponente racional no entero
        if b.n.is_const() and b.d.is_const():
            bv = b.n.const_value() / b.d.const_value()
            if bv < 0:
                # Convención del motor (dominio real): raíz real de índice impar; índice par requiere complejos
                if c.denominator % 2 == 0:
                    raise NotImplementedOperation("Potencia de un negativo con raíz de índice par: requiere complejos")
                try:
                    return _num_rf(arith._pow(-bv, c) * (-1 if c.numerator % 2 else 1))
                except NotImplementedOperation:
                    ctx.warnings.append("Raíz real de índice impar de un negativo (convención del dominio real)")
                    return _num_rf(-1 if c.numerator % 2 else 1) * _atom(f"({_fmt_frac(-bv)})^({c.numerator}/{c.denominator})")
            try:
                return _num_rf(arith._pow(bv, c))
            except NotImplementedOperation:
                pass
        if c == Fraction(1, 2): return _call(("call", "sqrt", [base_n]), ctx)
        ctx.ineqs.append(f"{rf_str(b.cancel())} >= 0")
        return _atom(f"{_wrap(rf_str(b.cancel()))}^({c.numerator}/{c.denominator})")
    e = to_rf(ex_n, ctx)
    return _atom(f"{_wrap(rf_str(b.cancel()))}^{_wrap(rf_str(e.cancel()))}")


_SIMPLE_TOKEN = _re.compile(r"^([A-Za-z_]\w*|\d+)$")


def _wrap(t):
    return t if _SIMPLE_TOKEN.match(t) else f"({t})"


def _monomial_sqrt(p):
    """√p si p es monomio con exponentes pares y coeficiente cuadrado perfecto; devuelve Poly o None."""
    if not p.is_monomial(): return None
    (m, c), = p.t.items()
    from .poly import _isqrt_exact
    if c <= 0: return None
    rn, rd = _isqrt_exact(c.numerator), _isqrt_exact(c.denominator)
    if rn is None or rd is None or any(e % 2 for _, e in m): return None
    return Poly({tuple((v, e // 2) for v, e in m): Fraction(rn, rd)})


def _sign_known(p, ctx):
    """+1 si p ≥ 0 conocido por supuestos, -1 si ≤ 0, 0 si desconocido. Solo monomios c·Πv^e."""
    if not p.is_monomial(): return 0
    (m, c), = p.t.items()
    s = 1 if c > 0 else -1
    for v, e in m:
        a = ctx.assumptions.get(v)
        if a == "positive": continue
        if a == "negative": s *= (-1) ** e; continue
        if e % 2 == 0: continue
        return 0
    return s


_SPECIAL_SIN6 = [0, 1, 2, 3, 2, 1, 0, -1, -2, -3, -2, -1]      # sin(j·π/6): 0,1/2,√3/2,1,... (índices en medios/√3 abajo)
_SIN_PI6 = ["0", "1/2", "r3/2", "1", "r3/2", "1/2", "0", "-1/2", "-r3/2", "-1", "-r3/2", "-1/2"]
_SIN_PI4 = ["0", "r2/2", "1", "r2/2", "0", "-r2/2", "-1", "-r2/2"]


def _exact_trig_value(token):
    neg = token.startswith("-"); t = token.lstrip("-")
    if t == "0": v = _num_rf(0)
    elif t == "1": v = _num_rf(1)
    elif t == "1/2": v = _num_rf(Fraction(1, 2))
    elif t == "r3/2": v = _num_rf(Fraction(1, 2)) * _atom("sqrt(3)")
    elif t == "r2/2": v = _num_rf(Fraction(1, 2)) * _atom("sqrt(2)")
    else: raise NotImplementedOperation("tabla trigonométrica")
    return -v if neg else v


def _trig_special(f, a):
    """sin/cos/tan exactos de múltiplos racionales de π con denominador 1,2,3,4,6; None si no aplica."""
    if not (a.d.is_const() and a.n.is_monomial()): return None
    (m, c), = a.n.t.items()
    if m != (("pi", 1),): return None
    q = c / a.d.const_value()
    for den, tab, step in ((6, _SIN_PI6, 12), (4, _SIN_PI4, 8)):
        k = q * den
        if k.denominator == 1:
            k = int(k) % step
            sin_t = tab[k]; cos_t = tab[(k + step // 4) % step]
            if f == "sin": return _exact_trig_value(sin_t)
            if f == "cos": return _exact_trig_value(cos_t)
            cv = _exact_trig_value(cos_t)
            if cv.is_zero(): raise MathDomainError("tan no está definida en múltiplos impares de π/2")
            return _exact_trig_value(sin_t) / cv
    return None


def _call(n, ctx):
    f = n[1]
    if f == "exp" and len(n[2]) == 1 and n[2][0][0] == "call" and n[2][0][1] == "ln" and len(n[2][0][2]) == 1:
        _call(n[2][0], ctx)              # registra u > 0
        return to_rf(n[2][0][2][0], ctx)  # exp(ln u) = u
    if f == "ln" and len(n[2]) == 1 and n[2][0][0] == "call" and n[2][0][1] == "exp" and len(n[2][0][2]) == 1:
        return to_rf(n[2][0][2][0], ctx)  # ln(exp u) = u (u real)
    if f not in {"sqrt", "abs", "sin", "cos", "tan", "exp", "ln", "asin", "acos", "atan", "sinh", "cosh", "tanh"}:
        raise NotImplementedOperation(f"Función '{f}' no soportada en expresiones simbólicas")
    if len(n[2]) != 1: raise NotImplementedOperation(f"Función '{f}' con {len(n[2])} argumentos no soportada")
    a = to_rf(n[2][0], ctx).cancel(ctx.warnings)
    const = a.n.is_const() and a.d.is_const()
    cv = a.n.const_value() / a.d.const_value() if const else None
    if f == "sqrt":
        if const:
            if cv < 0: raise NotImplementedOperation("Raíz de negativo requiere complejos")
            try: return _num_rf(arith._pow(cv, Fraction(1, 2)))
            except NotImplementedOperation:
                from .qsqrt import squarefree_split
                n_, m_ = cv.numerator, cv.denominator
                sq, dd = squarefree_split(n_ * m_)
                inner = _atom(f"sqrt({dd})")
                return _num_rf(Fraction(sq, m_)) * inner
        if a.d == Poly.const(1):
            q = _monomial_sqrt(a.n)
            if q is None:
                from .poly import u_sqrt
                vs = a.n.vars()
                if len(vs) == 1:
                    r = u_sqrt(a.n.to_upoly(vs[0]))
                    if r is not None: q = u_to_poly(r, vs[0])
            if q is not None:
                s = _sign_known(q, ctx)
                if s == 1: return RF(q)
                if s == -1: return RF(-q)
                return _atom(f"abs({rf_str(RF(q))})")
        ctx.ineqs.append(f"{rf_str(a)} >= 0")
        return _atom(f"sqrt({rf_str(a)})")
    if f == "abs":
        if const: return _num_rf(abs(cv))
        if a.d == Poly.const(1):
            s = _sign_known(a.n, ctx)
            if s == 1: return a
            if s == -1: return -a
        return _atom(f"abs({rf_str(a)})")
    special = {("sin", 0): 0, ("tan", 0): 0, ("cos", 0): 1, ("exp", 0): 1, ("ln", 1): 0,
               ("asin", 0): 0, ("atan", 0): 0, ("sinh", 0): 0, ("tanh", 0): 0, ("cosh", 0): 1, ("acos", 1): 0}
    if const and (f, cv) in special and cv.denominator == 1:
        return _num_rf(special[(f, cv)])
    if f in ("sin", "cos", "tan"):
        sp = _trig_special(f, a)
        if sp is not None: return sp
    if const and f == "ln" and cv <= 0:
        raise MathDomainError("ln de un valor no positivo")
    if const and f in ("asin", "acos") and abs(cv) > 1:
        raise MathDomainError(f"{f} fuera de [-1, 1]")
    if f == "ln" and not const:
        ctx.ineqs.append(f"{rf_str(a)} > 0")
    if f == "tan" and not _is_const_atom_expr(a):
        ctx.ineqs.append(f"cos({rf_str(a)}) != 0")
    if f in ("asin", "acos") and not const:
        ctx.ineqs.append(f"-1 <= {rf_str(a)} <= 1")
    return _atom(f"{f}({rf_str(a)})")


_CONST_ATOM = _re.compile(r"^(sqrt\(\d+\)|pi)$")


def _is_const_atom_expr(r):
    """True si r solo contiene constantes (pi, sqrt(d))."""
    return all(_CONST_ATOM.match(v) for v in set(r.n.vars()) | set(r.d.vars()))


def _const_atom_value(p):
    import math
    tot = 0.0
    for m, c in p.t.items():
        t = float(c)
        for v, e in m:
            t *= (math.pi if v == "pi" else math.sqrt(int(v[5:-1]))) ** e
        tot += t
    return tot


# ---------------- condiciones ----------------
def _fmt_frac(r):
    return str(r.numerator) if r.denominator == 1 else f"{r.numerator}/{r.denominator}"


def condition_list(conds, assumptions=None):
    """Convierte polinomios 'deben ser ≠0' en textos y descarta los garantizados por los supuestos."""
    assumptions = assumptions or {}
    out, seen = [], set()

    def add(text):
        if text not in seen: seen.add(text); out.append(text)

    for p in conds:
        if p.is_const(): continue
        if all(_CONST_ATOM.match(v) for v in p.vars()):
            if abs(_const_atom_value(p)) < 1e-12: raise MathDomainError("División por una constante que vale cero")
            continue        # constante no nula: no es una restricción
        c, mono, rest = p.content_and_monomial()
        for v, e in mono:
            if assumptions.get(v) in ("positive", "negative", "nonzero"): continue
            add(f"{v} ≠ 0")
        if rest.is_const(): continue
        vs = rest.vars()
        if len(vs) == 1:
            v = vs[0]
            sc, facs, complete = u_factor(rest.to_upoly(v))
            for f, mult in facs:
                if len(f) == 2:
                    r = -f[0] / f[1]
                    a = assumptions.get(v)
                    if a == "positive" and r <= 0: continue
                    if a == "negative" and r >= 0: continue
                    add(f"{v} ≠ {_fmt_frac(r)}")
                else:
                    add(f"{u_to_poly(f, v)} ≠ 0")
        else:
            add(f"{rest} ≠ 0")
    return out
