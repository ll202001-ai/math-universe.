"""Mini-CAS exacto para integrales iteradas.

Representación: Expr = suma de términos  coef(GP) · exp(E) · ∏ átomo^n,  con
  GP  = polinomio generalizado (exponentes racionales, p. ej. x^(1/2)), coeficientes Fraction; «pi» es una variable más.
  átomos: ln(A), sin(A), cos(A), pow(B, n) (B no monomial).
Todo es exacto (Fraction). Lo que no se pueda integrar lanza NoPrimitiva y el llamador usa cuadratura numérica."""
from fractions import Fraction
import math
from itertools import product as _prod

F = Fraction


_HAS_R = [False]
GREEK = {"pi": r"\pi", "theta": r"\theta", "phi": r"\varphi", "rho": r"\rho", "lambda": r"\lambda", "mu": r"\mu"}


def _reduce_r(t):
    """_rN = √N  (N libre de cuadrados):  _rN^e → N^(e//2)·_rN^(e%2)"""
    out = {}
    for m, c in t.items():
        nm, cc = [], c
        for n, e in m:
            if n.startswith("_r"):
                N = int(n[2:]); q, r = divmod(e, 2)
                if q.denominator != 1: nm.append((n, e)); continue
                cc = cc * (F(N) ** int(q)); e = r
                if e == 0: continue
            nm.append((n, e))
        k = tuple(sorted(nm)); out[k] = out.get(k, 0) + cc
    return {m: c for m, c in out.items() if c != 0}


def raiz_gp(N):
    """GP de √N con N entero positivo (extrae cuadrados)"""
    N = F(N); num, den = N.numerator, N.denominator
    def sqf(n):
        f = _factor_int(n); a = 1; b = 1
        for p, k in f.items():
            a *= p ** (k // 2); b *= p ** (k % 2)
        return a, b
    a1, b1 = sqf(num); a2, b2 = sqf(den)
    # √(num/den) = (a1/a2)·√(b1/b2) = (a1/(a2·b2))·√(b1·b2)
    sq = b1 * b2
    coef = F(a1, a2 * b2)
    if sq == 1: return GP.const(coef)
    _HAS_R[0] = True
    return GP({((f"_r{sq}", F(1)),): coef})


class NoPrimitiva(Exception):
    pass


class NoSoportado(Exception):
    pass


# =============================================================== polinomios generalizados
class GP:
    __slots__ = ("t",)

    def __init__(self, t=None):
        t = {m: c for m, c in (t or {}).items() if c != 0}
        if _HAS_R[0] and any(n.startswith("_r") for m in t for n, _ in m):
            t = _reduce_r(t)
        self.t = t

    @staticmethod
    def const(c): return GP({(): F(c)})

    @staticmethod
    def var(n): return GP({((n, F(1)),): F(1)})

    def copy(self): return GP(dict(self.t))

    def key(self): return tuple(sorted(self.t.items()))

    def is_zero(self): return not self.t

    def is_const(self): return all(m == () for m in self.t)

    def cval(self): return self.t.get((), F(0))

    def vars(self): return {v for m in self.t for v, _ in m}

    def has(self, v): return any(v == a for m in self.t for a, _ in m)

    def __add__(self, o):
        o = _g(o); r = dict(self.t)
        for m, c in o.t.items():
            r[m] = r.get(m, 0) + c
        return GP(r)

    __radd__ = __add__

    def __neg__(self): return GP({m: -c for m, c in self.t.items()})

    def __sub__(self, o): return self + (-_g(o))

    def __rsub__(self, o): return _g(o) + (-self)

    def __mul__(self, o):
        o = _g(o); r = {}
        for m1, c1 in self.t.items():
            for m2, c2 in o.t.items():
                m = _mmul(m1, m2); r[m] = r.get(m, 0) + c1 * c2
        return GP(r)

    __rmul__ = __mul__

    def __eq__(self, o):
        try: return self.key() == _g(o).key()
        except Exception: return False

    def __hash__(self): return hash(self.key())

    def ipow(self, n):
        if n < 0: raise NoSoportado("potencia negativa")
        r = GP.const(1)
        for _ in range(n): r = r * self
        return r

    def is_mono(self): return len(self.t) == 1

    def mono_pow(self, r):
        """(c·∏x^a)^r para monomio y r racional; c^r debe ser racional."""
        (m, c), = self.t.items()
        r = F(r)
        mm = tuple((v, a * r) for v, a in m)
        if r.denominator == 1:
            cc = c ** int(r) if r >= 0 else F(1) / (c ** int(-r))
        else:
            try:
                cc = _rat_root(c, r)
            except NoSoportado:
                if r.denominator != 2 or c < 0: raise
                base = raiz_gp(c).ipow(abs(r.numerator))
                if r < 0: base = base.inv()
                return GP({mm: F(1)}) * base
        return GP({mm: cc})

    def inv(self):
        if not self.is_mono(): raise NoSoportado("división por un polinomio no monomio")
        return self.mono_pow(-1)

    def subs(self, v, g):
        g = _g(g); out = GP(); cache = {}
        for m, c in self.t.items():
            a = next((e for n, e in m if n == v), None)
            rest = GP({tuple((n, e) for n, e in m if n != v): c})
            if a is None: out = out + rest; continue
            if a.denominator == 1 and a >= 0:
                key = int(a)
                if key not in cache: cache[key] = g.ipow(key)
                out = out + rest * cache[key]
            elif g.is_zero() and a > 0:
                continue
            elif g.is_mono():
                out = out + rest * g.mono_pow(a)
            else:
                raise NoSoportado("sustitución con exponente no entero de un polinomio")
        return out

    def deriv(self, v):
        r = {}
        for m, c in self.t.items():
            a = next((e for n, e in m if n == v), None)
            if a is None: continue
            nm = tuple((n, (e - 1 if n == v else e)) for n, e in m if not (n == v and e == 1))
            r[nm] = r.get(nm, 0) + c * a
        return GP(r)

    def coef_in(self, v):
        """{exponente de v: GP resto}"""
        d = {}
        for m, c in self.t.items():
            a = next((e for n, e in m if n == v), F(0))
            rest = tuple((n, e) for n, e in m if n != v)
            d.setdefault(a, GP()); d[a] = d[a] + GP({rest: c})
        return d

    def eval(self, env):
        s = 0.0
        for m, c in self.t.items():
            p = float(c)
            for n, e in m:
                x = env[n] if n in env else (math.pi if n == "pi" else (math.sqrt(int(n[2:])) if n.startswith("_r") else None))
                if x is None: raise KeyError(n)
                if x < 0 and e.denominator != 1: raise ValueError("raíz de negativo")
                p *= x ** float(e)
            s += p
        return s

    def integ(self, v):
        r = {}
        for m, c in self.t.items():
            a = next((e for n, e in m if n == v), F(0))
            if a == -1: raise NoPrimitiva("1/x requiere ln")
            nm = tuple(sorted([(n, e) for n, e in m if n != v] + [(v, a + 1)]))
            r[nm] = r.get(nm, 0) + c / (a + 1)
        return GP(r)

    # ----- impresión
    def _terms(self):
        def ordk(it):
            m, c = it
            return (-sum(abs(e) for _, e in m) if False else 0, tuple((n, -e) for n, e in m))
        items = sorted(self.t.items(), key=lambda it: (-max([e for _, e in it[0]] or [0]), it[0]))
        return items

    def to_str(self, latex=False):
        if not self.t: return "0"
        out = []
        for i, (m, c) in enumerate(self._terms()):
            s = _term_str(c, m, latex)
            neg = s.startswith("-")
            body = s[1:] if neg else s
            out.append(("-" if neg else "+", body))
        res = ("-" if out[0][0] == "-" else "") + out[0][1]
        for sg, b in out[1:]: res += f" {sg} {b}"
        return res

    __str__ = to_str


def _g(x): return x if isinstance(x, GP) else GP.const(F(x))


def _mmul(a, b):
    d = dict(a)
    for n, e in b:
        d[n] = d.get(n, 0) + e
    return tuple(sorted((n, e) for n, e in d.items() if e != 0))


def _rat_root(c, r):
    p, q = r.numerator, r.denominator
    if c < 0: raise NoSoportado("raíz de negativo")
    def iroot(n, k):
        x = round(n ** (1.0 / k)) if n > 0 else 0
        for y in (x - 1, x, x + 1):
            if y >= 0 and y ** k == n: return y
        return None
    a, b = iroot(c.numerator, q), iroot(c.denominator, q)
    if a is None or b is None: raise NoSoportado("coeficiente sin raíz racional")
    base = F(a, b)
    return base ** p if p >= 0 else F(1) / base ** (-p)


def _fs(c, latex):
    if c.denominator == 1: return str(abs(c.numerator))
    return (r"\frac{%d}{%d}" % (abs(c.numerator), c.denominator)) if latex else f"{abs(c.numerator)}/{c.denominator}"


def _term_str(c, m, latex):
    sign = "-" if c < 0 else ""
    num, den = [], []
    for n, e in m:
        nm = (GREEK.get(n, n) if latex else n)
        if e > 0: num.append(_pw(nm, e, latex))
        else: den.append(_pw(nm, -e, latex))
    ac = abs(c)
    if latex:
        N = ("" if (ac.numerator == 1 and (num or den)) else str(ac.numerator)) + "".join(num)
        N = N or "1"
        D = (str(ac.denominator) if ac.denominator != 1 else "") + "".join(den)
        return sign + (N if not D else r"\frac{%s}{%s}" % (N, D))
    parts = []
    if ac.numerator != 1 or not (num or den): parts.append(str(ac.numerator))
    parts += num
    s = "*".join(parts) if parts else "1"
    if ac.denominator != 1: s += "/" + str(ac.denominator)
    if den: s += "/" + ("*".join(den) if len(den) == 1 else "(" + "*".join(den) + ")")
    return sign + s


def _pw(nm, e, latex):
    if nm.startswith("_r"):
        N = nm[2:]
        base = (r"\sqrt{%s}" % N) if latex else f"√{N}"
        return base if e == 1 else (f"({base})^{e}")
    if e == 1: return nm
    if e.denominator == 1: return f"{nm}^{{{e.numerator}}}" if latex else f"{nm}^{e.numerator}"
    if latex and e == F(1, 2): return r"\sqrt{%s}" % nm
    return f"{nm}^{{{_fs(e, True)}}}" if latex else f"{nm}^({e.numerator}/{e.denominator})"


# =============================================================== Expr
def _gk(key): return GP(dict(key))


class Expr:
    """dict {(Ekey, atoms): GP}.  Ekey=() sin exponencial.  atoms = tuple ordenada de (tipo, argkey, n)"""
    __slots__ = ("t",)

    def __init__(self, t=None):
        self.t = {k: c for k, c in (t or {}).items() if not c.is_zero()}

    @staticmethod
    def of(x):
        if isinstance(x, Expr): return x
        return Expr({((), ()): _g(x)}) if not isinstance(x, GP) else Expr({((), ()): x})

    def __add__(self, o):
        o = Expr.of(o); r = dict(self.t)
        for k, c in o.t.items():
            r[k] = r[k] + c if k in r else c
        return Expr(r)

    __radd__ = __add__

    def __neg__(self): return Expr({k: -c for k, c in self.t.items()})

    def __sub__(self, o): return self + (-Expr.of(o))

    def __rsub__(self, o): return Expr.of(o) - self

    def __mul__(self, o):
        o = Expr.of(o); r = {}
        for (e1, a1), c1 in self.t.items():
            for (e2, a2), c2 in o.t.items():
                e = (_gk(e1) + _gk(e2)).key() if (e1 or e2) else ()
                c = c1 * c2
                atoms, extra = _merge_atoms(a1, a2)
                if extra is not None: c = c * extra
                k = (e, atoms)
                r[k] = r[k] + c if k in r else c
        return Expr(r)

    __rmul__ = __mul__

    def is_zero(self): return not self.t

    def gp(self):
        """Si es un GP puro lo devuelve, si no lanza NoSoportado."""
        if not self.t: return GP()
        if len(self.t) == 1 and ((), ()) in self.t: return self.t[((), ())]
        raise NoSoportado("no es un polinomio")

    def is_gp(self): return not self.t or (len(self.t) == 1 and ((), ()) in self.t)

    def has(self, v):
        for (e, a), c in self.t.items():
            if c.has(v) or (e and _gk(e).has(v)) or any(_gk(ak).has(v) for _, ak, _ in a): return True
        return False

    def subs(self, v, g):
        g = Expr.of(g)
        out = Expr()
        gpure = g.is_gp()
        for (e, a), c in self.t.items():
            if not c.has(v): term = Expr.of(c)
            elif gpure: term = Expr.of(c.subs(v, g.gp()))
            else:
                term = Expr()
                for ex, rest in c.coef_in(v).items():
                    term = term + Expr.of(rest) * (_epow(g, ex) if ex != 0 else Expr.of(1))
            if e:
                if not gpure and _gk(e).has(v): raise NoSoportado("exp con argumento no polinómico")
                term = term * mk_exp(_gk(e).subs(v, g.gp()) if _gk(e).has(v) else _gk(e))
            for kind, ak, n in a:
                if _gk(ak).has(v):
                    if not gpure: raise NoSoportado("función de un argumento no polinómico")
                    A = _gk(ak).subs(v, g.gp())
                else: A = _gk(ak)
                term = term * _atom_pow(kind, A, n)
            out = out + term
        return out

    def deriv(self, v):
        out = Expr()
        for (e, a), c in self.t.items():
            base_atoms = [(k, _gk(ak), n) for k, ak, n in a]
            core = Expr.of(1)
            if e: core = core * mk_exp(_gk(e))
            for k, A, n in base_atoms: core = core * _atom_pow(k, A, n)
            out = out + Expr.of(c.deriv(v)) * core + Expr.of(c) * _core_deriv(e, base_atoms, v)
        return out

    def eval(self, env):
        s = 0.0
        for (e, a), c in self.t.items():
            p = c.eval(env)
            if e: p *= math.exp(_gk(e).eval(env))
            for k, ak, n in a:
                x = _gk(ak).eval(env)
                if k == "ln": p *= math.log(x) ** float(n)
                elif k == "sin": p *= math.sin(x) ** float(n)
                elif k == "cos": p *= math.cos(x) ** float(n)
                else:
                    if x < 0 and F(n).denominator != 1: raise ValueError("raíz de negativo")
                    if x == 0 and n < 0: raise ZeroDivisionError
                    p *= x ** float(n)
            s += p
        return s

    def to_str(self, latex=False):
        if not self.t: return "0"
        parts = []
        for (e, a), c in sorted(self.t.items(), key=lambda it: (len(it[0][1]), bool(it[0][0]), it[0])):
            parts.append(_expr_term(c, e, a, latex))
        res = parts[0]
        for p in parts[1:]:
            res += (" - " + p[1:]) if p.startswith("-") else (" + " + p)
        return res

    __str__ = to_str


def _expr_term(c, e, a, latex):
    facs = []
    if e: facs.append(_exp_str(_gk(e), latex))
    for k, ak, n in a:
        A = _gk(ak); s = A.to_str(latex)
        if k == "pow":
            base = f"({s})" if not latex else r"\left(%s\right)" % s
            nn = F(n)
            if latex:
                if nn == -1: facs.append(("/", base)); continue
                facs.append(("p", f"{base}^{{{_fs(nn, True) if nn.denominator != 1 else nn.numerator}}}")); continue
            facs.append(f"{base}^{n}" if nn.denominator == 1 else f"{base}^({nn.numerator}/{nn.denominator})")
        else:
            nm = {"ln": r"\ln" if latex else "ln", "sin": r"\sin" if latex else "sin", "cos": r"\cos" if latex else "cos"}[k]
            arg = s if (len(A.t) == 1 and (latex or True)) else s
            body = (f"{nm}({arg})" if not latex else (r"%s\left(%s\right)" % (nm, arg) if not A.is_mono() else f"{nm}({arg})"))
            nn = F(n)
            facs.append(body if nn == 1 else (f"{body}^{{{nn.numerator}}}" if latex else f"{body}^{nn.numerator}"))
    # coeficiente
    cs = c.to_str(latex)
    if not facs: return cs
    plain = [f for f in facs if isinstance(f, str)]
    den = [f[1] for f in facs if isinstance(f, tuple) and f[0] == "/"]
    pw = [f[1] for f in facs if isinstance(f, tuple) and f[0] == "p"]
    plain += pw
    if len(c.t) == 1:
        sign = "-" if cs.startswith("-") else ""
        body = cs[1:] if sign else cs
        if body == "1": body = ""
        core = ("" if not body else body + ("" if latex else "*")) + (("" if latex else "*").join(plain))
        core = core.strip("*") or "1"
    else:
        sign = ""
        core = ("(" + cs + ")") + ("" if latex else "*") + (("" if latex else "*").join(plain))
        core = core.strip("*")
    if den:
        d = "".join(den) if latex else "*".join(den)
        return sign + (r"\frac{%s}{%s}" % (core or "1", d) if latex else f"{core}/{d}")
    return sign + core


def _exp_str(E, latex):
    if E.is_const() and E.cval() == 1: return "e" if not latex else "e"
    return ("e^{%s}" % E.to_str(True)) if latex else f"e^({E.to_str()})"


def _merge_atoms(a1, a2):
    d = {}
    for k, ak, n in a1 + a2:
        d[(k, ak)] = d.get((k, ak), 0) + F(n)
    extra = GP.const(1); res = []
    for (k, ak), n in d.items():
        if n == 0: continue
        if k == "pow" and n.denominator == 1 and n > 0:
            extra = extra * _gk(ak).ipow(int(n)); continue
        res.append((k, ak, n))
    res.sort()
    return tuple(res), (None if extra == GP.const(1) else extra)


def _core_deriv(e, atoms, v):
    """derivada de exp(E)·∏átomos^n (sin el coeficiente)"""
    out = Expr()
    items = ([("exp", _gk(e), 1)] if e else []) + [(k, A, n) for k, A, n in atoms]
    for i, (k, A, n) in enumerate(items):
        dA = A.deriv(v)
        if dA.is_zero(): continue
        if k == "exp": d = mk_exp(A)
        elif k == "ln": d = (_atom_pow("pow", A, -1)) * (F(n) * _atom_pow("ln", A, n - 1) if n != 1 else Expr.of(1))
        elif k == "sin": d = F(n) * _atom_pow("sin", A, n - 1) * _atom_pow("cos", A, 1)
        elif k == "cos": d = -F(n) * _atom_pow("cos", A, n - 1) * _atom_pow("sin", A, 1)
        else: d = F(n) * _atom_pow("pow", A, n - 1)
        rest = Expr.of(1)
        for j, (k2, A2, n2) in enumerate(items):
            if j != i: rest = rest * (mk_exp(A2) if k2 == "exp" else _atom_pow(k2, A2, n2))
        out = out + rest * d * Expr.of(dA)
    return out


# ----------------------------------------------------------------- constructores de átomos
_PRIMES = None


def _factor_int(n):
    f = {}; d = 2
    while d * d <= n:
        while n % d == 0: f[d] = f.get(d, 0) + 1; n //= d
        d += 1
    if n > 1: f[n] = f.get(n, 0) + 1
    return f


def mk_exp(A):
    A = _g(A)
    if A.is_zero(): return Expr.of(1)
    return Expr({(A.key(), ()): GP.const(1)})


def mk_ln(A, n=1):
    A = _g(A)
    if A.is_zero(): raise NoSoportado("ln(0)")
    if A.is_mono():
        (m, c), = A.t.items()
        if c <= 0: raise NoSoportado("ln de negativo")
        out = Expr()
        parts = Expr()
        terms = []
        for p, k in _factor_int(c.numerator).items(): terms.append((GP.const(p), F(k)))
        for p, k in _factor_int(c.denominator).items(): terms.append((GP.const(p), F(-k)))
        for v, e in m: terms.append((GP.var(v), e))
        tot = Expr()
        for A_, k in terms: tot = tot + Expr({((), (("ln", A_.key(), F(1)),)): GP.const(k)})
        if n != 1:
            if len(terms) == 0: return Expr.of(0)
            if len(terms) == 1:
                A_, k = terms[0]; return Expr({((), (("ln", A_.key(), F(n)),)): GP.const(k ** n)})
            r = Expr.of(1)
            for _ in range(n): r = r * tot
            return r
        return tot
    return Expr({((), (("ln", A.key(), F(n)),)): GP.const(1)})


def _pi_mult(A):
    """Si A = r·pi (racional r) devuelve r, si no None"""
    if A.is_zero(): return F(0)
    if len(A.t) == 1:
        (m, c), = A.t.items()
        if m == (("pi", F(1)),): return c
    return None


def _trig_exacto(kind, r):
    """sin/cos de r·π para r con denominador 1,2,3,4,6 → GP (con √2, √3) o None"""
    r = F(r) % 2
    if r.denominator not in (1, 2, 3, 4, 6): return None
    k = int(r * 12)                      # múltiplos de π/12 → solo los de π/6 y π/4 y π/2
    # ángulo de referencia en el primer cuadrante y signos
    ang = r
    sg_s = sg_c = 1
    if ang > 1: ang = ang - 1; sg_s = -1; sg_c = -1
    if ang > F(1, 2): ang = 1 - ang; sg_c = -sg_c
    tabla = {F(0): (GP.const(0), GP.const(1)), F(1, 6): (GP.const(F(1, 2)), raiz_gp(3) * F(1, 2)),
             F(1, 4): (raiz_gp(2) * F(1, 2), raiz_gp(2) * F(1, 2)), F(1, 3): (raiz_gp(3) * F(1, 2), GP.const(F(1, 2))),
             F(1, 2): (GP.const(1), GP.const(0))}
    if ang not in tabla: return None
    sn, cs = tabla[ang]
    return sn * sg_s if kind == "sin" else cs * sg_c


def mk_trig(kind, A, n=1):
    A = _g(A)
    pm = _pi_mult(A)
    if A.is_zero():
        return Expr.of(0 if kind == "sin" else 1) if n > 0 else None
    if pm is not None:
        v = _trig_exacto(kind, pm)
        if v is not None:
            r = Expr.of(v)
            out = Expr.of(1)
            for _ in range(int(n)): out = out * r
            return out
    # normalizar signo del argumento (sin impar, cos par)
    sign = 1
    if A.t and next(iter(sorted(A.t.items())))[1] < 0 and kind == "sin" and n % 2 == 1:
        A = -A; sign = -1
    elif A.t and next(iter(sorted(A.t.items())))[1] < 0 and kind == "cos":
        A = -A
    return Expr({((), ((kind, A.key(), F(n)),)): GP.const(sign)})


def mk_pow(B, n):
    B = _g(B); n = F(n)
    if B.is_zero():
        if n > 0: return Expr.of(0)
        raise NoSoportado("división por cero")
    if B.is_mono(): return Expr.of(B.mono_pow(n))
    if n.denominator == 1 and n >= 0: return Expr.of(B.ipow(int(n)))
    return Expr({((), (("pow", B.key(), n),)): GP.const(1)})


def _atom_pow(kind, A, n):
    n = F(n)
    if n == 0: return Expr.of(1)
    if kind == "exp": return mk_exp(A * int(n))
    if kind == "ln": return mk_ln(A, int(n))
    if kind in ("sin", "cos"): return mk_trig(kind, A, int(n))
    return mk_pow(A, n)


# ----------------------------------------------------------------- AST → Expr
def from_ast(n):
    k = n[0]
    if k == "num": return Expr.of(n[1])
    if k == "sym": return Expr.of(GP.var(n[1]))
    if k == "neg": return -from_ast(n[1])
    if k == "bin":
        op = n[1]
        a, b = from_ast(n[2]), from_ast(n[3])
        if op == "+": return a + b
        if op == "-": return a - b
        if op == "*": return a * b
        if op == "/": return a * _inverse(b)
        if op == "^":
            # exponente racional constante
            try: r = b.gp()
            except NoSoportado: r = None
            if r is None or not r.is_const():
                if n[2] == ("sym", "e") or (n[2][0] == "num" and False):
                    return mk_exp(b.gp())
                raise NoSoportado("exponente variable")
            return _power(a, r.cval())
    if k == "call":
        f, args = n[1], n[2]
        if f in ("sen",): f = "sin"
        if f == "exp": return mk_exp(from_ast(args[0]).gp())
        if f in ("ln", "log") and len(args) == 1: return mk_ln(from_ast(args[0]).gp())
        if f == "sqrt": return _power(from_ast(args[0]), F(1, 2))
        if f in ("sin", "cos"): return mk_trig(f, from_ast(args[0]).gp())
    raise NoSoportado("función no soportada por el integrador exacto")


def _epow(g, a):
    """g^a para Expr g (a racional): entero ≥0 por multiplicación; racional si g = monomio·pow(B,n)"""
    a = F(a)
    if a.denominator == 1 and a >= 0:
        r = Expr.of(1)
        for _ in range(int(a)): r = r * g
        return r
    if len(g.t) == 1:
        (e, at), c = next(iter(g.t.items()))
        if not e and c.is_mono() and all(k == "pow" for k, _, _ in at):
            res = Expr.of(c.mono_pow(a))
            for k, ak, nn in at: res = res * mk_pow(_gk(ak), nn * a)
            return res
    raise NoSoportado("potencia no entera de una expresión no polinómica")


def _inverse(b):
    return _power(b, F(-1))


def _power(a, r):
    if not a.is_gp() and r.denominator != 1:
        try:
            a2 = pitag(a)
            if a2.is_gp(): a = a2
        except Exception:
            pass
    if r.denominator == 1 and r >= 0 and not a.is_gp():
        out = Expr.of(1)
        for _ in range(int(r)): out = out * a
        return out
    if a.is_gp():
        g = a.gp()
        if r.denominator == 1 and r >= 0: return Expr.of(g.ipow(int(r)))
        if g.is_mono(): return Expr.of(g.mono_pow(r))
        return mk_pow(g, r)
    # átomo único sin coeficiente raro
    if len(a.t) == 1:
        (e, at), c = next(iter(a.t.items()))
        if not at and e and c.is_mono() and r.denominator == 1:
            return Expr({((_gk(e) * int(r)).key(), ()): c.mono_pow(r)})
        if r.denominator == 1 and c.is_mono() and all(k == "pow" for k, _, _ in at) and not e:
            res = Expr.of(c.mono_pow(r))
            for k, ak, nn in at: res = res * mk_pow(_gk(ak), nn * r)
            return res
    raise NoSoportado("potencia de una expresión no polinómica")


def pitag(e):
    """sin²A + cos²A = 1 (combina términos con igual coeficiente)."""
    t = dict(e.t)

    def mk(atoms, over):
        d = {}
        for k, ak, n in atoms: d[(k, ak)] = n
        for kk, nn in over.items(): d[kk] = nn
        return tuple(sorted((k, ak, n) for (k, ak), n in d.items() if n != 0))
    changed = True
    while changed:
        changed = False
        for key, c in list(t.items()):
            if key not in t: continue
            ex, atoms = key
            for (k, ak, n) in atoms:
                if k != "sin" or n < 2: continue
                m = next((n2 for k2, ak2, n2 in atoms if k2 == "cos" and ak2 == ak), 0)
                pkey = (ex, mk(atoms, {("sin", ak): n - 2, ("cos", ak): m + 2}))
                if pkey != key and pkey in t and t[pkey] == c:
                    bkey = (ex, mk(atoms, {("sin", ak): n - 2}))
                    del t[key]; del t[pkey]
                    t[bkey] = t[bkey] + c if bkey in t else c
                    changed = True
                    break
            if changed: break
        if changed:
            t = {k: v for k, v in t.items() if not v.is_zero()}
    return Expr(t)
