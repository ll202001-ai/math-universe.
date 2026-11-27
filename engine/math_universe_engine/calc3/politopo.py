"""Integración exacta sobre politopos (regiones limitadas por desigualdades LINEALES en 2D o 3D).

Cubre triángulos, polígonos, tetraedros, pirámides, prismas, paralelepípedos, regiones con |x|+|y| ≤ c, etc., y permite
elegir cualquier orden de integración. La región se parte automáticamente en «rebanadas» en las que los límites son
funciones afines y constantes de combinatoria; cada pieza es una integral iterada exacta (cas3). Es un algoritmo general
(descomposición celular por vértices y cortes), no una plantilla por ejercicio.
"""
import itertools
from fractions import Fraction as F
from ..parser import parse
from ..ast_tools import normalize
from .cas3 import from_ast, GP, Expr, NoSoportado
from .iterada import integrar


def _P(s): return from_ast(normalize(parse(s)))


def afin(s, vs):
    """expresión lineal → ({v: coef}, const) con Fractions; None si no es afín en vs"""
    try:
        g = _P(s).gp()
    except Exception:
        return None
    coefs = {}; rest = g
    for v in vs:
        cs = g.coef_in(v)
        if any(k not in (F(0), F(1)) for k in cs): return None
        a = cs.get(F(1))
        if a is None: coefs[v] = F(0); continue
        if not a.is_const(): return None
        coefs[v] = a.cval()
        rest = rest - GP.var(v) * GP.const(coefs[v])
    if not rest.is_const(): return None
    return coefs, rest.cval()


def _ev(a, pt):
    c, k = a
    return sum(c[v] * pt.get(v, 0) for v in c) + k


def _sub(a, b):
    return ({v: a[0][v] - b[0][v] for v in a[0]}, a[1] - b[1])


def _neg(a): return ({v: -x for v, x in a[0].items()}, -a[1])


def _resolver_sistema(filas, rhs):
    n = len(filas)
    M = [list(f) + [r] for f, r in zip(filas, rhs)]
    for c in range(n):
        p = next((r for r in range(c, n) if M[r][c] != 0), None)
        if p is None: return None
        M[c], M[p] = M[p], M[c]
        pv = M[c][c]; M[c] = [x / pv for x in M[c]]
        for r in range(n):
            if r != c and M[r][c] != 0:
                fct = M[r][c]; M[r] = [x - fct * y for x, y in zip(M[r], M[c])]
    return [M[i][n] for i in range(n)]


def vertices(cons, vs):
    d = len(vs); out = set()
    for sub in itertools.combinations(range(len(cons)), d):
        filas = [[cons[i][0][v] for v in vs] for i in sub]
        sol = _resolver_sistema(filas, [-cons[i][1] for i in sub])
        if sol is None: continue
        pt = dict(zip(vs, sol))
        if all(_ev(c, pt) >= 0 for c in cons): out.add(tuple(sol))
    return sorted(out)


def _fm(cons, v):
    """elimina la variable v (Fourier–Motzkin)"""
    pos = [c for c in cons if c[0][v] > 0]; neg = [c for c in cons if c[0][v] < 0]; cero = [c for c in cons if c[0][v] == 0]
    out = list(cero)
    for p in pos:
        for q in neg:
            a, b = p[0][v], -q[0][v]
            out.append(({w: p[0][w] * b + q[0][w] * a for w in p[0]}, p[1] * b + q[1] * a))
    return out


def _cotas(cons, v):
    """(inferiores, superiores): v ≥ afín(otras) / v ≤ afín(otras)"""
    lo = []; hi = []
    for c, k in cons:
        a = c[v]
        if a == 0: continue
        otros = {w: -x / a for w, x in c.items() if w != v}
        otros[v] = F(0)
        (lo if a > 0 else hi).append((otros, -k / a))
    return lo, hi


def _normaliza(cons):
    out = []; vistos = set()
    for c, k in cons:
        g = max([abs(x) for x in c.values()] + [abs(k)])
        if g == 0: continue
        cc = {v: x / g for v, x in c.items()}; kk = k / g
        key = (tuple(sorted(cc.items())), kk)
        if key not in vistos: vistos.add(key); out.append((cc, kk))
    return out


def _afin_str(a, vs):
    c, k = a
    t = []
    for v in vs:
        if c.get(v, 0) != 0: t.append(f"({c[v]})*{v}")
    if k != 0 or not t: t.append(f"({k})")
    return "+".join(t)


def _recta_y(a, b):
    """y = afín(x) tal que a(x,y) = b(x,y) (lista vacía si no depende de y)"""
    d = _sub(a, b)
    cy = d[0].get("y", F(0))
    if cy == 0: return None
    return ({w: -x / cy for w, x in d[0].items() if w != "y"}, -d[1] / cy)


def _interseccion_x(r1, r2):
    """x donde dos rectas y=afín(x) coinciden (o None)"""
    dx = r1[0].get("x", F(0)) - r2[0].get("x", F(0)); dk = r1[1] - r2[1]
    if dx == 0: return None
    return -dk / dx


def piezas(cons, orden):
    """→ lista de piezas; cada pieza = lista de (var, lo, hi) de EXTERNA a INTERNA con lo/hi afines en las externas"""
    vs = list(orden); d = len(vs)
    cons = _normaliza(cons)
    for c, _ in cons:
        for v in vs: c.setdefault(v, F(0))
    V = vertices(cons, vs)
    if len(V) < d + 1: raise NoSoportado("La región lineal está vacía, degenerada o no acotada")
    x, y, z = (vs + [None, None])[:3]
    # --- 2D
    if d == 1: raise NoSoportado("Se necesitan al menos dos variables")
    xs = sorted({v[0] for v in V})
    if d == 2:
        lo, hi = _cotas(cons, vs[1])
        brk = set(xs)
        rl = [(a, b) for a, b in itertools.combinations(lo, 2)] + [(a, b) for a, b in itertools.combinations(hi, 2)]
        for a, b in rl:
            dx = a[0].get(vs[0], F(0)) - b[0].get(vs[0], F(0))
            if dx != 0:
                t = -(a[1] - b[1]) / dx
                if xs[0] < t < xs[-1]: brk.add(t)
        brk = sorted(brk); out = []
        for xa, xb in zip(brk, brk[1:]):
            m = {vs[0]: (xa + xb) / 2}
            li = max(lo, key=lambda a: _ev(a, m)); ls = min(hi, key=lambda a: _ev(a, m))
            if _ev(ls, m) <= _ev(li, m): continue
            out.append([(vs[0], F(xa), F(xb)), (vs[1], li, ls)])
        return out
    # --- 3D: rebanadas en x; en cada una, franjas en y; límites z con combinatoria fija
    c2 = _normaliza(_fm(cons, vs[2]))
    zlo, zhi = _cotas(cons, vs[2])
    ylo, yhi = _cotas(c2, vs[1])
    # rectas y = afín(x) candidatas
    rectas = []
    def add(r):
        if r is not None and r not in rectas: rectas.append(r)
    for a, b in itertools.combinations(zlo, 2): add(_recta_y(_zafin(a, vs), _zafin(b, vs)))
    for a, b in itertools.combinations(zhi, 2): add(_recta_y(_zafin(a, vs), _zafin(b, vs)))
    for a in ylo + yhi: add(({vs[0]: a[0].get(vs[0], F(0))}, a[1]))
    rectas = [({vs[0]: r[0].get(vs[0], F(0)), "y": F(0)}, r[1]) if False else r for r in rectas]
    brk = set(xs)
    for r1, r2 in itertools.combinations([_re(r, vs) for r in rectas], 2):
        t = _interseccion_x(r1, r2)
        if t is not None and xs[0] < t < xs[-1]: brk.add(t)
    brk = sorted(brk); out = []
    for xa, xb in zip(brk, brk[1:]):
        xm = (xa + xb) / 2; m = {vs[0]: xm}
        yl = max(ylo, key=lambda a: _ev(_ya(a, vs), m)); yh = min(yhi, key=lambda a: _ev(_ya(a, vs), m))
        yl = _ya(yl, vs); yh = _ya(yh, vs)
        vl, vh = _ev(yl, m), _ev(yh, m)
        if vh <= vl: continue
        cortes = [(vl, yl), (vh, yh)]
        for r in rectas:
            rr = _re(r, vs); val = _ev(rr, m)
            if vl < val < vh: cortes.append((val, rr))
        cortes.sort(key=lambda t: t[0])
        # eliminar duplicados (mismo valor en xm ⇒ misma recta en la rebanada)
        lim = []
        for v, r in cortes:
            if not lim or v != lim[-1][0]: lim.append((v, r))
        for (v1, r1), (v2, r2) in zip(lim, lim[1:]):
            pt = {vs[0]: xm, vs[1]: (v1 + v2) / 2}
            zl = max(zlo, key=lambda a: _ev(_zafin(a, vs), pt)); zh = min(zhi, key=lambda a: _ev(_zafin(a, vs), pt))
            zl, zh = _zafin(zl, vs), _zafin(zh, vs)
            if _ev(zh, pt) <= _ev(zl, pt): continue
            out.append([(vs[0], F(xa), F(xb)), (vs[1], r1, r2), (vs[2], zl, zh)])
    return out


def _zafin(a, vs):
    c, k = a
    return ({v: c.get(v, F(0)) for v in vs[:2]}, k)


def _ya(a, vs):
    c, k = a
    return ({vs[0]: c.get(vs[0], F(0))}, k)


def _re(r, vs):
    c, k = r
    return ({vs[0]: c.get(vs[0], F(0))}, k)


def _num(a):
    c, k = a
    return None


def integrar_politopo(cons, orden, f, nombre="I"):
    """cons: [(coefs, const)] con Σ coef·v + const ≥ 0. Devuelve dict como iterada.integrar (suma de piezas)"""
    pz = piezas(cons, orden)
    if not pz: raise NoSoportado("La región no tiene interior")
    fe = _P(f)
    total = None; aprox = 0.0; ver_ok = True; hay_ver = True; pasos = []
    for i, pieza in enumerate(pz, 1):
        niv = []
        for var, lo, hi in reversed(pieza):
            niv.append({"var": var, "lo": _P(_afin_str(lo, orden)) if isinstance(lo, tuple) and isinstance(lo[0], dict) else _P(str(lo)),
                        "hi": _P(_afin_str(hi, orden)) if isinstance(hi, tuple) and isinstance(hi[0], dict) else _P(str(hi))})
        r = integrar(fe, niv, nombre=nombre)
        if r["exacto"] is None: raise NoSoportado("Una pieza no tiene primitiva elemental")
        total = r["exacto"] if total is None else total + r["exacto"]
        aprox += r["aprox"]
        ver_ok = ver_ok and r.get("verificacion") == "passed"
        pasos.append({"text": f"Pieza {i} de {len(pz)}" if len(pz) > 1 else "Planteamiento", "latex": None})
        pasos.extend(r["pasos"])
    if len(pz) > 1:
        pasos.insert(0, {"text": f"La región se divide en {len(pz)} piezas donde los límites son funciones afines (cada pieza es una integral iterada); el resultado es la suma."})
        pasos.append({"text": "Suma de las piezas", "latex": total.to_str(True)})
    return {"exacto": total, "aprox": aprox, "pasos": pasos, "verificacion": "passed" if ver_ok else "not_possible", "piezas": len(pz),
            "planteamiento": None}


def restricciones_desde_textos(desigs, vs):
    """['x+y<=1', '0<=z<=2', 'abs(x)+abs(y)<=1', …] → lista de (coefs, const) afines (≥0) o None si no son lineales"""
    cons = []
    for s in desigs:
        import re
        partes = re.split(r"(<=|>=|<|>)", s)
        exprs = [p.strip() for p in partes[0::2]]; ops = partes[1::2]
        for k, op in enumerate(ops):
            a, b = exprs[k], exprs[k + 1]
            if op in ("<", "<="): a, b = b, a
            g = f"({a})-({b})"            # g ≥ 0
            c = _abs_expandido(g, vs)
            if c is None: return None
            cons.extend(c)
    return cons


def _abs_expandido(g, vs):
    import re
    if "abs(" not in g:
        a = afin(g, vs)
        return None if a is None else [a]
    # g = c − Σ w_i |l_i| con w_i > 0  ⇒  c − Σ w_i σ_i l_i ≥ 0 para todos los signos σ
    ast = normalize(parse(g))
    terminos = []
    def rec(nd, sg):
        if nd[0] == "bin" and nd[1] == "+": rec(nd[2], sg); rec(nd[3], sg)
        elif nd[0] == "bin" and nd[1] == "-": rec(nd[2], sg); rec(nd[3], -sg)
        elif nd[0] == "neg": rec(nd[1], -sg)
        elif nd[0] == "call" and nd[1] == "abs": terminos.append((sg, nd[2][0]))
        elif nd[0] == "bin" and nd[1] == "*" and nd[2][0] == "num" and nd[3][0] == "call" and nd[3][1] == "abs":
            terminos.append((sg * F(str(nd[2][1])), nd[3][2][0]))
        else: terminos.append((sg, nd))
    rec(ast, 1)
    from ..ast_tools import to_str as ast_str
    absT = [(w, a) for w, a in [(t[0], t[1]) for t in terminos]]
    # separar términos abs y resto: los abs vienen como call; reconocer de nuevo
    solo_abs = []; resto = []
    def rec2(nd, sg):
        if nd[0] == "bin" and nd[1] == "+": rec2(nd[2], sg); rec2(nd[3], sg)
        elif nd[0] == "bin" and nd[1] == "-": rec2(nd[2], sg); rec2(nd[3], -sg)
        elif nd[0] == "neg": rec2(nd[1], -sg)
        elif nd[0] == "call" and nd[1] == "abs": solo_abs.append((sg, nd[2][0]))
        elif nd[0] == "bin" and nd[1] == "*" and nd[2][0] == "num" and nd[3][0] == "call" and nd[3][1] == "abs":
            solo_abs.append((sg * F(str(nd[2][1])), nd[3][2][0]))
        else: resto.append((sg, nd))
    rec2(ast, 1)
    if not solo_abs or any(w > 0 for w, _ in solo_abs): return None      # solo regiones convexas: c − Σ w|l| ≥ 0
    out = []
    for signos in itertools.product((1, -1), repeat=len(solo_abs)):
        partes = [("(" + ast_str(nd) + ")") if sg > 0 else ("-(" + ast_str(nd) + ")") for sg, nd in resto]
        for (w, a), s in zip(solo_abs, signos):
            partes.append(f"({-w * s})*({ast_str(a)})")        # w<0 ⇒ −w>0
            # (g contiene  w·|a|  con w<0;  w·|a| ≥ ... se acota por  w·s·a  con s=±1 ⇒ término  w*s*a)
        # reconstruir: g_σ = resto + Σ w_i σ_i a_i  (w_i<0)
        partes = [("(" + ast_str(nd) + ")") if sg > 0 else ("-(" + ast_str(nd) + ")") for sg, nd in resto]
        for (w, a), s in zip(solo_abs, signos): partes.append(f"({w * s})*({ast_str(a)})")
        a = afin("+".join(partes) if partes else "0", vs)
        if a is None: return None
        out.append(a)
    return out
