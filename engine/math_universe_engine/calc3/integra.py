"""Integración indefinida exacta respecto de una variable sobre Expr (reglas del curso)."""
from fractions import Fraction as F
from .cas3 import (GP, Expr, NoPrimitiva, NoSoportado, mk_exp, mk_ln, mk_trig, mk_pow, _gk, _g, _atom_pow)


def _split(e, a, v):
    """separa átomos independientes de v (constantes) de los que dependen de v"""
    const, dep = [], []
    for k, ak, n in a:
        (dep if _gk(ak).has(v) else const).append((k, ak, n))
    return tuple(const), tuple(dep)


def _build(c, e, atoms):
    t = Expr.of(c)
    if e: t = t * mk_exp(_gk(e))
    for k, ak, n in atoms: t = t * _atom_pow(k, _gk(ak), n)
    return t


def exact_div(a, b):
    """a / b como GP si b divide exactamente a (orden lexicográfico); si no, None"""
    if b.is_zero(): return None
    rem = a.copy(); q = GP()
    bl = max(b.t.items(), key=lambda it: _ordk(it[0]))
    for _ in range(200):
        if rem.is_zero(): return q
        rl = max(rem.t.items(), key=lambda it: _ordk(it[0]))
        m = _msub(rl[0], bl[0])
        t = GP({m: rl[1] / bl[1]})
        q = q + t; rem = rem - t * b
    return None


def _ordk(m): return tuple(sorted((n, e) for n, e in m))


def _msub(a, b):
    d = dict(a)
    for n, e in b: d[n] = d.get(n, 0) - e
    return tuple(sorted((n, e) for n, e in d.items() if e != 0))


def _lin(A, v):
    """A = g·v + h con g, h libres de v → (g, h) o None"""
    cs = A.coef_in(v)
    if any(e not in (0, 1) for e in cs): return None
    return cs.get(F(1), GP()), cs.get(F(0), GP())


def integrate(expr, v):
    """∫ expr dv  → Expr (sin constante).  Lanza NoPrimitiva."""
    out = Expr()
    for (e, a), c in expr.t.items():
        out = out + _term(c, e, a, v)
    return out


def _term(c, e, a, v):
    cst, dep = _split(a, a, v)
    ehas = bool(e) and _gk(e).has(v)
    if not (c.has(v) or ehas or dep):
        return Expr.of(c * GP.var(v)) * _build(GP.const(1), e, a)
    K = lambda extra=GP.const(1): _build(extra, (), cst) if not e or ehas else _build(extra, e, cst)
    # --- sin átomos dependientes ni exp dependiente: polinomio generalizado
    if not dep and not ehas:
        base = _build(GP.const(1), e, cst)
        cs = c.coef_in(v)
        res = Expr()
        for ex, rest in cs.items():
            if ex == -1:
                res = res + Expr.of(rest) * mk_ln(GP.var(v))
            else:
                res = res + Expr.of(rest * GP({((v, ex + 1),): F(1) / (ex + 1)}))
        return res * base
    # --- exp con exponente dependiente, sin otros átomos dependientes
    base = _build(GP.const(1), (), cst)
    if ehas and not dep:
        E = _gk(e)
        r = _int_exp(c, E, v)
        return r * base
    if ehas:
        raise NoPrimitiva("producto exp·función no soportado")
    # --- potencias de seno y coseno del mismo argumento (coeficiente sin la variable)
    if dep and not e and all(k in ("sin", "cos") for k, _, _ in dep) and len({ak for _, ak, _ in dep}) == 1 \
            and not (len(dep) == 1 and dep[0][2] == 1 and (c.has(v))):
        if c.has(v): raise NoPrimitiva("potencias trigonométricas con coeficiente variable")
        A = _gk(dep[0][1]); m = sum(int(n) for k, _, n in dep if k == "sin"); nn = sum(int(n) for k, _, n in dep if k == "cos")
        lin = _lin(A, v)
        if lin is None or lin[0].is_zero() or not lin[0].is_mono(): raise NoPrimitiva("argumento trigonométrico no lineal")
        if m < 0 or nn < 0: raise NoPrimitiva("potencia negativa de sen/cos")
        return Expr.of(c) * _sincos(m, nn, A, v, lin[0].inv()) * base
    # --- un solo átomo dependiente
    if len(dep) != 1 or e:
        raise NoPrimitiva("producto de funciones no soportado")
    k, ak, n = dep[0]; A = _gk(ak)
    if k in ("sin", "cos") and n == 1:
        return _int_trig(c, k, A, v) * base
    if k == "pow":
        return _int_pow(c, A, F(n), v) * base
    if k == "ln":
        return _int_ln(c, A, int(n), v) * base
    raise NoPrimitiva("átomo no soportado")


def _chain(c, dA):
    """c = k·dA con k libre de la variable  → k (GP) o None"""
    return exact_div(c, dA)


def _int_exp(c, E, v):
    lin = _lin(E, v)
    if lin is not None and not lin[0].is_zero():
        g, h = lin
        if not g.is_mono(): raise NoPrimitiva("exp con coeficiente no monomio")
        ginv = g.inv(); cs = c.coef_in(v)
        if any(ex.denominator != 1 or ex < 0 for ex in cs): raise NoPrimitiva("exp con potencia no entera")
        # ∫ v^n e^{gv+h} = e^{E} Σ_k (-1)^k n!/(n-k)! v^{n-k} / g^{k+1}
        poly = GP()
        for ex, rest in cs.items():
            n = int(ex); f = F(1)
            for kk in range(n + 1):
                term = GP({((v, F(n - kk)),): F(1)}) if n - kk != 0 else GP.const(1)
                poly = poly + rest * term * ginv.ipow(kk + 1) * (F((-1) ** kk) * f)
                f *= (n - kk)
        return Expr.of(poly) * mk_exp(E)
    k = _chain(c, E.deriv(v))
    if k is not None and not k.has(v): return Expr.of(k) * mk_exp(E)
    # E = a·v² + h  con coeficiente v^n (n impar): por partes  ∫ v^n e^{a v²} = v^{n-1} e^{E}/(2a) − (n−1)/(2a) ∫ v^{n−2} e^{E}
    cs_e = E.coef_in(v)
    if set(cs_e) <= {F(0), F(2)} and F(2) in cs_e and cs_e[F(2)].is_mono():
        a2 = cs_e[F(2)]; inv2a = (a2 * 2).inv(); cs = c.coef_in(v); res = Expr()
        for ex, rest in cs.items():
            if ex.denominator != 1 or ex < 1 or int(ex) % 2 == 0: raise NoPrimitiva("potencia par con exp(v²): no elemental")
            n = int(ex)
            term = Expr.of(rest * GP({((v, F(n - 1)),): F(1)}) * inv2a) * mk_exp(E) if n > 1 else Expr.of(rest * inv2a) * mk_exp(E)
            res = res + term
            if n > 1:
                res = res - integrate(Expr.of(rest * GP({((v, F(n - 2)),): F(1)}) * inv2a * (n - 1)) * mk_exp(E), v)
        return res
    raise NoPrimitiva("exp no integrable con las reglas disponibles")


def _int_trig(c, kind, A, v):
    lin = _lin(A, v)
    if lin is not None and not lin[0].is_zero():
        g, h = lin
        if not g.is_mono(): raise NoPrimitiva("trig con coeficiente no monomio")
        ginv = g.inv(); cs = c.coef_in(v)
        if any(ex.denominator != 1 or ex < 0 for ex in cs): raise NoPrimitiva("trig con potencia no entera")
        res = Expr()
        for ex, rest in cs.items():
            res = res + Expr.of(rest) * _int_vn_trig(int(ex), kind, A, v, ginv)
        return res
    k = _chain(c, A.deriv(v))
    if k is not None and not k.has(v):
        return Expr.of(k) * (mk_trig("sin", A) if kind == "cos" else -mk_trig("cos", A))
    raise NoPrimitiva("trig no integrable con las reglas disponibles")


def _int_vn_trig(n, kind, A, v, ginv):
    vn = GP({((v, F(n)),): F(1)}) if n else GP.const(1)
    if kind == "sin":
        first = -mk_trig("cos", A) * Expr.of(vn * ginv)
        if n == 0: return first
        return first + Expr.of(ginv * n) * _int_vn_trig(n - 1, "cos", A, v, ginv)
    first = mk_trig("sin", A) * Expr.of(vn * ginv)
    if n == 0: return first
    return first - Expr.of(ginv * n) * _int_vn_trig(n - 1, "sin", A, v, ginv)


def _int_pow(c, B, n, v):
    """∫ c(v)·B^n dv con B lineal en v"""
    lin = _lin(B, v)
    if lin is not None and not lin[0].is_zero():
        q, p = lin
        if not q.is_mono(): raise NoPrimitiva("denominador con coeficiente no monomio")
        qinv = q.inv(); cs = c.coef_in(v)
        if any(ex.denominator != 1 or ex < 0 for ex in cs): raise NoPrimitiva("potencia no entera en el numerador")
        # desplazar c(v) a potencias de (v + p/q):  c(v) = Σ d_k (v + s)^k, s = p/q
        s = p * qinv
        coefs = [GP() for _ in range(int(max(cs)) + 1)] if cs else []
        for ex, rest in cs.items(): coefs[int(ex)] = coefs[int(ex)] + rest
        d = []
        cur = coefs[:]
        while cur:
            # división sintética por (v - r) con r = -s
            r = -s; m = len(cur); b = [GP() for _ in range(m)]
            b[m - 1] = cur[m - 1]
            for i in range(m - 2, -1, -1): b[i] = cur[i] + r * b[i + 1]
            d.append(b[0]); cur = b[1:]
        res = Expr()
        for kk, dk in enumerate(d):
            expo = F(kk) + n
            # (v+s)^k = (B/q)^k ; dv = dB/q
            coef = dk * qinv.ipow(kk + 1) if True else None
            if expo == -1: res = res + Expr.of(coef) * mk_ln(B)
            else: res = res + Expr.of(coef * GP.const(F(1) / (expo + 1))) * mk_pow(B, expo + 1)
        return res
    dB = B.deriv(v)
    k = _chain(c, dB)
    if k is not None and not k.has(v):
        if n == -1: return Expr.of(k) * mk_ln(B)
        return Expr.of(k * GP.const(F(1) / (n + 1))) * mk_pow(B, n + 1)
    raise NoPrimitiva("potencia de polinomio no integrable con las reglas disponibles")


def _int_ln(c, A, n, v):
    cs = c.coef_in(v)
    if any(ex.denominator != 1 for ex in cs): raise NoPrimitiva("ln con potencia no entera")
    # ln(v)^n con 1/v:  ∫ v^-1 ln^n = ln^{n+1}/(n+1)
    if A == GP.var(v) and set(cs) == {F(-1)}:
        return Expr.of(cs[F(-1)] * GP.const(F(1, n + 1))) * mk_ln(A, n + 1)
    if n != 1:
        if A != GP.var(v): raise NoPrimitiva("potencia de ln no soportada")
        res = Expr()
        for ex, rest in cs.items():
            if ex == -1:
                res = res + Expr.of(rest * GP.const(F(1, n + 1))) * mk_ln(A, n + 1)
                continue
            vn1 = GP({((v, ex + 1),): F(1) / (ex + 1)})
            res = res + Expr.of(rest * vn1) * mk_ln(A, n)
            sub = Expr.of(rest * GP({((v, ex),): F(1)}) * GP.const(F(n) / (ex + 1))) * mk_ln(A, n - 1)
            res = res - integrate(sub, v)
        return res
    res = Expr()
    for ex, rest in cs.items():
        if ex == -1:
            raise NoPrimitiva("ln(B)/v con B no monomio")
        vn1 = GP({((v, ex + 1),): F(1) / (ex + 1)})
        res = res + Expr.of(rest * vn1) * mk_ln(A)
        # - ∫ vn1·A'/A dv   (rational)
        dA = A.deriv(v)
        num = rest * vn1 * dA
        res = res - integrate(Expr.of(num) * mk_pow(A, -1), v)
    return res


def _polmul(p, q):
    r = [F(0)] * (len(p) + len(q) - 1)
    for i, a in enumerate(p):
        for j, b in enumerate(q): r[i + j] += a * b
    return r


def _polpow(p, k):
    r = [F(1)]
    for _ in range(k): r = _polmul(r, p)
    return r


def _sincos(m, n, A, v, ginv):
    """∫ sin(A)^m cos(A)^n dv con A lineal en v (ginv = 1/(dA/dv))"""
    one = Expr.of(1)
    if m % 2 == 1:
        k = (m - 1) // 2
        p = _polmul(_polpow([F(1), F(0), F(-1)], k), [F(0)] * n + [F(1)])       # (1-u²)^k u^n
        res = Expr()
        for j, a in enumerate(p):
            if a: res = res + Expr.of(ginv * (-a / (j + 1))) * mk_trig("cos", A, j + 1)
        return res
    if n % 2 == 1:
        k = (n - 1) // 2
        p = _polmul(_polpow([F(1), F(0), F(-1)], k), [F(0)] * m + [F(1)])
        res = Expr()
        for j, a in enumerate(p):
            if a: res = res + Expr.of(ginv * (a / (j + 1))) * mk_trig("sin", A, j + 1)
        return res
    if m == 0 and n == 0:
        return Expr.of(GP.var(v))
    # ambos pares: sin²=(1-c2)/2, cos²=(1+c2)/2 con c2 = cos(2A)
    p = _polmul(_polpow([F(1, 2), F(-1, 2)], m // 2), _polpow([F(1, 2), F(1, 2)], n // 2))
    A2 = A * 2; ginv2 = ginv * F(1, 2)
    res = Expr()
    for j, a in enumerate(p):
        if not a: continue
        res = res + Expr.of(a) * (Expr.of(GP.var(v)) if j == 0 else _sincos(0, j, A2, v, ginv2))
    return res
