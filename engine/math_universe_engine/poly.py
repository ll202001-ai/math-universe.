"""Polinomios multivariantes con coeficientes racionales exactos + utilidades univariantes.

Monomio: tupla ordenada de (variable, exponente>0). Poly: {monomio: Fraction}.
Los "átomos" (sin(x), sqrt(2), pi...) se tratan como variables adicionales.
"""
from fractions import Fraction
from math import gcd
from . import limits
from .errors import LimitExceeded, MathDomainError, NotImplementedOperation


def _mmul(a, b):
    if not a: return b
    if not b: return a
    d = dict(a)
    for v, e in b:
        d[v] = d.get(v, 0) + e
    return tuple(sorted(d.items()))


def _mdiv(a, b):
    """a/b si b divide a, si no None."""
    d = dict(a)
    for v, e in b:
        if d.get(v, 0) < e: return None
        d[v] -= e
        if d[v] == 0: del d[v]
    return tuple(sorted(d.items()))


def _mkey(m):  # orden: grado total desc, luego lexicográfico
    return (-sum(e for _, e in m), [(v, -e) for v, e in m])


_CALL_RE = None


def _atom_txt(v):
    """Texto de una 'variable' de Poly para imprimir. Los átomos con forma de potencia (x^a, 2^a, (x+1)^a) se
    parentetizan: sin ello (x^a)^2 se imprimiría x^a^2, que se lee x^(a^2) (potencias asocian a la derecha)."""
    global _CALL_RE
    import re
    if _CALL_RE is None: _CALL_RE = re.compile(r"^[A-Za-z_]\w*\(")
    if v.isidentifier(): return v
    if _CALL_RE.match(v):
        depth = 0
        for i, ch in enumerate(v):                     # forma f(...) con el paréntesis inicial cerrado al final: segura
            if ch == "(": depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0: return v if i == len(v) - 1 else f"({v})"
    return f"({v})"


class Poly:
    __slots__ = ("t",)

    def __init__(self, t=None):
        self.t = {m: c for m, c in (t or {}).items() if c != 0}

    @staticmethod
    def const(c): return Poly({(): Fraction(c)})

    @staticmethod
    def var(n): return Poly({((n, 1),): Fraction(1)})

    def is_zero(s): return not s.t
    def is_const(s): return all(m == () for m in s.t)
    def const_value(s): return s.t.get((), Fraction(0))
    def copy(s): return Poly(dict(s.t))

    def vars(s):
        return sorted({v for m in s.t for v, _ in m})

    def degree(s, v=None):
        if not s.t: return -1
        if v is None: return max(sum(e for _, e in m) for m in s.t)
        return max(dict(m).get(v, 0) for m in s.t)

    def __add__(s, o):
        o = _p(o); r = dict(s.t)
        for m, c in o.t.items():
            r[m] = r.get(m, 0) + c
        return Poly(r)

    __radd__ = __add__
    def __neg__(s): return Poly({m: -c for m, c in s.t.items()})
    def __sub__(s, o): return s + (-_p(o))
    def __rsub__(s, o): return _p(o) - s

    def __mul__(s, o):
        o = _p(o); r = {}
        for m1, c1 in s.t.items():
            limits.check()
            for m2, c2 in o.t.items():
                m = _mmul(m1, m2)
                r[m] = r.get(m, 0) + c1 * c2
        limits.check_size(len(r))
        return Poly(r)

    __rmul__ = __mul__

    def __pow__(s, n):
        if n < 0: raise MathDomainError("Exponente negativo en polinomio")
        if n > limits.MAX_POW: raise LimitExceeded("Exponente demasiado grande", {"max": limits.MAX_POW})
        r, b = Poly.const(1), s
        while n:
            if n & 1: r = r * b
            n >>= 1
            if n: b = b * b
        return r

    def __eq__(s, o): return s.t == _p(o).t
    def __hash__(s): return hash(frozenset(s.t.items()))

    def scale(s, c): return Poly({m: v * c for m, v in s.t.items()})

    def diff(s, v):
        r = {}
        for m, c in s.t.items():
            d = dict(m); e = d.get(v, 0)
            if e == 0: continue
            if e == 1: del d[v]
            else: d[v] = e - 1
            mm = tuple(sorted(d.items()))
            r[mm] = r.get(mm, 0) + c * e
        return Poly(r)

    def subs(s, v, q):
        """Sustituye la variable v por el polinomio q."""
        q = _p(q); r = Poly(); cache = {}
        for m, c in s.t.items():
            d = dict(m); e = d.pop(v, 0)
            base = Poly({tuple(sorted(d.items())): c})
            if e:
                if e not in cache: cache[e] = q ** e
                base = base * cache[e]
            r = r + base
        return r

    def coeffs_in(s, v):
        """{grado: Poly} respecto de v (coeficientes en las demás variables)."""
        r = {}
        for m, c in s.t.items():
            d = dict(m); e = d.pop(v, 0)
            mm = tuple(sorted(d.items()))
            r.setdefault(e, {})[mm] = c
        return {e: Poly(t) for e, t in r.items()}

    def content_and_monomial(s):
        """(c, mono, resto): s = c·mono·resto con resto primitivo-entero y signo del término líder positivo."""
        if not s.t: return Fraction(0), (), Poly()
        mono = None
        for m in s.t:
            if mono is None: mono = dict(m)
            else:
                mono = {v: min(e, dict(m).get(v, 0)) for v, e in mono.items() if dict(m).get(v, 0) > 0}
        mono = tuple(sorted(mono.items()))
        stripped = {_mdiv(m, mono): c for m, c in s.t.items()}
        nums = [c.numerator for c in stripped.values()]; dens = [c.denominator for c in stripped.values()]
        g = 0
        for n in nums: g = gcd(g, abs(n))
        l = 1
        for d in dens: l = l * d // gcd(l, d)
        c = Fraction(g, l)
        lead = stripped[min(stripped, key=_mkey)]
        if lead < 0: c = -c
        return c, mono, Poly({m: v / c for m, v in stripped.items()})

    def lead_term(s):
        m = min(s.t, key=_mkey)
        return m, s.t[m]

    def exact_div(s, q):
        """Cociente exacto s/q (división multivariante), o None si q no divide a s."""
        if q.is_zero(): raise MathDomainError("División por cero")
        qm, qc = q.lead_term(); rem = s.copy(); quo = {}
        steps = 0
        while not rem.is_zero():
            limits.check(); steps += 1
            if steps > 100000: raise LimitExceeded("División demasiado larga")
            rm, rc = rem.lead_term()
            tm = _mdiv(rm, qm)
            if tm is None: return None
            tc = rc / qc
            quo[tm] = quo.get(tm, 0) + tc
            rem = rem - q * Poly({tm: tc})
        return Poly(quo)

    def evaluate(s, env):
        """Evalúa con env {var: valor (Fraction/Q)}; todas las variables deben estar."""
        total = 0
        for m, c in s.t.items():
            term = c
            for v, e in m:
                term = term * (env[v] ** e)
            total = total + term
        return total

    def to_upoly(s, v):
        """Lista de coeficientes (índice=grado) si solo interviene la variable v."""
        if any(x != v for x in s.vars()):
            raise NotImplementedOperation("Polinomio no univariante")
        n = s.degree(v)
        out = [Fraction(0)] * (n + 1)
        for m, c in s.t.items():
            out[dict(m).get(v, 0)] = c
        return out

    # ---- impresión ----
    def __str__(s):
        if not s.t: return "0"
        terms = sorted(s.t.items(), key=lambda kv: _mkey(kv[0]))
        out = ""
        for i, (m, c) in enumerate(terms):
            mono = "*".join(_atom_txt(v) if e == 1 else f"{_atom_txt(v)}^{e}" for v, e in m)
            a = abs(c)
            cs = str(a.numerator) if a.denominator == 1 else f"({a.numerator}/{a.denominator})"
            if not m: body = cs if a.denominator == 1 else f"{a.numerator}/{a.denominator}"
            elif a == 1: body = mono
            else: body = f"{cs}*{mono}"
            if i == 0: out = ("-" if c < 0 else "") + body
            else: out += (" - " if c < 0 else " + ") + body
        return out

    __repr__ = __str__

    def is_monomial(s): return len(s.t) == 1


def _p(o):
    return o if isinstance(o, Poly) else Poly.const(o)


# ================= Univariante: listas de Fraction (índice = grado) =================
def u_trim(a):
    a = list(a)
    while a and a[-1] == 0: a.pop()
    return a


def u_add(a, b):
    n = max(len(a), len(b)); return u_trim([(a[i] if i < len(a) else 0) + (b[i] if i < len(b) else 0) for i in range(n)])


def u_sub(a, b):
    return u_add(a, [-x for x in b])


def u_mul(a, b):
    if not a or not b: return []
    r = [Fraction(0)] * (len(a) + len(b) - 1)
    for i, x in enumerate(a):
        limits.check()
        for j, y in enumerate(b): r[i + j] += x * y
    return u_trim(r)


def u_divmod(a, b):
    a = u_trim(a); b = u_trim(b)
    if not b: raise MathDomainError("División por polinomio cero")
    q = [Fraction(0)] * max(len(a) - len(b) + 1, 0); r = list(a)
    while len(r) >= len(b) and r:
        limits.check()
        k = len(r) - len(b); c = r[-1] / b[-1]; q[k] = c
        for i, y in enumerate(b): r[i + k] -= c * y
        r = u_trim(r)
    return u_trim(q), r


def u_gcd(a, b):
    a, b = u_trim(a), u_trim(b)
    while b:
        limits.check()
        a, b = b, u_divmod(a, b)[1]
    return [x / a[-1] for x in a] if a else []


def u_eval(a, x):
    r = 0
    for c in reversed(a): r = r * x + c
    return r


def u_deriv(a): return u_trim([i * c for i, c in enumerate(a)][1:])


def u_to_poly(a, v):
    return Poly({((v, i),) if i else (): c for i, c in enumerate(a)})


def u_primitive_int(a):
    """(escala, lista de enteros primitivos con coef. líder > 0): a = escala · ints."""
    l = 1
    for c in a: l = l * c.denominator // gcd(l, c.denominator)
    ints = [int(c * l) for c in a]
    g = 0
    for n in ints: g = gcd(g, abs(n))
    ints = [n // g for n in ints]
    if ints[-1] < 0: ints = [-n for n in ints]; sc = Fraction(-g, l)
    else: sc = Fraction(g, l)
    return sc, ints


def _divisors(n):
    n = abs(n)
    if n == 0: return []
    fac = {}; p = 2; m = n
    while p * p <= m:
        limits.check()
        while m % p == 0: fac[p] = fac.get(p, 0) + 1; m //= p
        p += 1 if p == 2 else 2
        if p > 5_000_000: raise NotImplementedOperation("Entero demasiado grande para factorizar")
    if m > 1: fac[m] = fac.get(m, 0) + 1
    ds = [1]
    for pr, e in fac.items():
        ds = [d * pr ** k for d in ds for k in range(e + 1)]
        if len(ds) > 200000: raise LimitExceeded("Demasiados divisores")
    return sorted(ds)


def rational_roots(a):
    """Raíces racionales distintas de un polinomio univariante (lista de Fraction)."""
    a = u_trim(a)
    if len(a) <= 1: return []
    _, ints = u_primitive_int(a)
    roots = []
    if ints[0] == 0:
        roots.append(Fraction(0))
        k = next(i for i, c in enumerate(ints) if c != 0); ints = ints[k:]
    if len(ints) > 1:
        for p in _divisors(ints[0]):
            for q in _divisors(ints[-1]):
                for sgn in (1, -1):
                    limits.check()
                    r = Fraction(sgn * p, q)
                    if r not in roots and u_eval([Fraction(c) for c in ints], r) == 0:
                        roots.append(r)
    return sorted(roots)


_KRON_CAP = 400000


def _lagrange(xs, ys):
    """Coeficientes (lista, índice=grado) del polinomio que interpola (xs, ys), con Fractions exactas."""
    n = len(xs)
    coef = [Fraction(0)] * n
    for i in range(n):
        num = [Fraction(1)]; den = Fraction(1)
        for j in range(n):
            if j == i: continue
            num = u_mul(num, [Fraction(-xs[j]), Fraction(1)]); den *= (xs[i] - xs[j])
        for k, c in enumerate(num):
            coef[k] += ys[i] * c / den
    return coef


def _kronecker_degree(ints, k):
    """Busca un factor entero primitivo de grado k de un polinomio entero (método de Kronecker).
    Devuelve (factor|None, agotado). `agotado` = True si se superó el tope de candidatos: NO se puede afirmar que no exista."""
    p = [Fraction(c) for c in ints]
    xs, vals = [], []
    x = 0
    while len(xs) < k + 1:
        v = u_eval(p, Fraction(x))
        if v != 0: xs.append(x); vals.append(int(v))
        x = -x if x > 0 else -x + 1            # 0, 1, -1, 2, -2, ...
        if abs(x) > 60: return None, True
    divs = [_divisors(abs(v)) for v in vals]
    lc = abs(int(p[-1]))
    cand = 0
    import itertools
    for ys_abs in itertools.product(*divs):
        for signs in itertools.product((1, -1), repeat=k):       # el primer valor se toma positivo (q y -q son el mismo factor)
            cand += 1
            if cand > _KRON_CAP: return None, True
            if cand % 256 == 0: limits.check()
            ys = [Fraction(ys_abs[0])] + [Fraction(sg * y) for sg, y in zip(signs, ys_abs[1:])]
            q = _lagrange(xs, ys)
            if q[k] == 0 or any(c.denominator != 1 for c in q): continue
            if lc % abs(int(q[k])) != 0: continue
            _, rem = u_divmod(p, q)
            if not rem: return q, False
    return None, False


def u_factor(a):
    """Factoriza un polinomio univariante sobre Q.
    Devuelve (constante, [(factor_lista, multiplicidad)], completo). Método: raíces racionales + Kronecker por grado
    (2 .. n/2), que es exhaustivo; completo=False solo si se agotó el tope de candidatos (no se afirma irreducibilidad)."""
    a = u_trim(a)
    if not a: return Fraction(0), [], True
    sc, ints = u_primitive_int(a)
    cur = [Fraction(c) for c in ints]
    factors = []; complete = True
    for r in rational_roots(cur):
        mult = 0; lin = [-r, Fraction(1)]
        while len(cur) > 1:
            q, rem = u_divmod(cur, lin)
            if rem: break
            cur = q; mult += 1
        # normalizar factor lineal a entero primitivo
        _, li = u_primitive_int(lin)
        s2, _ = u_primitive_int(lin)
        factors.append(([Fraction(c) for c in li], mult))
        sc *= s2 ** mult
    # restantes: sin raíces racionales
    if len(cur) == 1: sc *= cur[0]      # constante residual tras extraer factores lineales
    stack = [cur] if len(cur) > 1 else []
    while stack:
        f = stack.pop(); d = len(f) - 1
        if d <= 3:
            _, fi = u_primitive_int(f); s2, _ = u_primitive_int(f)
            factors.append(([Fraction(c) for c in fi], 1)); sc *= s2; continue
        s2, fi = u_primitive_int(f)
        found = None
        for k in range(2, d // 2 + 1):
            q, agotado = _kronecker_degree(fi, k)
            if q is not None: found = q; break
            if agotado: complete = False       # no se puede afirmar irreducibilidad: se informa, no se oculta
        if found is not None:
            quo, rem = u_divmod(f, found); stack.append(found); stack.append(quo)
        else:
            factors.append(([Fraction(c) for c in fi], 1)); sc *= s2
    # agrupar iguales
    merged = {}
    for f, m in factors:
        merged[tuple(f)] = merged.get(tuple(f), 0) + m
    out = sorted(((list(k), v) for k, v in merged.items()), key=lambda kv: (len(kv[0]), kv[0]))
    return sc, out, complete


def u_sqrt(a):
    """Raíz cuadrada polinómica exacta (lista) o None si a no es un cuadrado perfecto en Q[x]."""
    a = u_trim(a)
    if not a: return []
    if (len(a) - 1) % 2: return None
    n = (len(a) - 1) // 2
    # raíz del coeficiente líder
    lc = a[-1]
    if lc <= 0: return None
    rn, rd = _isqrt_exact(lc.numerator), _isqrt_exact(lc.denominator)
    if rn is None or rd is None: return None
    q = [Fraction(0)] * (n + 1); q[n] = Fraction(rn, rd)
    for k in range(n - 1, -1, -1):
        # coef de x^{n+k} en q² = suma i+j=n+k
        s = sum(q[i] * q[n + k - i] for i in range(k + 1, n + 1) if 0 <= n + k - i <= n)
        q[k] = (a[n + k] - s) / (2 * q[n])
    return q if u_trim(u_mul(q, q)) == a else None


def _isqrt_exact(n):
    from math import isqrt
    r = isqrt(n); return r if r * r == n else None
