"""Jacobianos y cambio de variables en integrales dobles y triples (formato de clase)."""
from fractions import Fraction as F
from ..parser import parse
from ..ast_tools import normalize, free_symbols
from .cas3 import GP, Expr, NoSoportado, from_ast, pitag
from .iterada import integrar, lat, _fmt_num
from .aplicaciones import integral_region
from .numerico import compile_ast
from ..ast_tools import subs as ast_subs
from .curvas import _gp_ast


def _P(s): return from_ast(normalize(parse(s)))


def _gp(s): return _P(s).gp()


def _det(M):
    n = len(M)
    if n == 1: return M[0][0]
    if n == 2: return M[0][0] * M[1][1] - M[0][1] * M[1][0]
    out = Expr()
    for j in range(n):
        minor = [[M[i][k] for k in range(n) if k != j] for i in range(1, n)]
        term = M[0][j] * _det(minor)
        out = out + (term if j % 2 == 0 else -term)
    return out


def jacobiano_matriz(old, new, mapa):
    """mapa: {old_i: Expr en las new}. Devuelve (matriz de Expr, determinante simplificado)"""
    M = [[mapa[o].deriv(v) for v in new] for o in old]
    return M, pitag(_det(M))


def _lat_matriz(M):
    return r"\begin{vmatrix}" + r" \\ ".join(" & ".join(lat(c) for c in row) for row in M) + r"\end{vmatrix}"


def _resolver_lineal(old, new, defs):
    """new_j = Σ a_ji·old_i + b_j  (GP lineal) → old_i = Σ … (GP en new). Aritmética exacta."""
    n = len(old)
    A = [[F(0)] * n for _ in range(n)]; b = [GP() for _ in range(n)]
    for j, nv in enumerate(new):
        g = defs[nv]
        for m, c in g.t.items():
            if m == (): b[j] = b[j] + GP.const(c); continue
            if len(m) == 1 and m[0][1] == 1 and m[0][0] in old: A[j][old.index(m[0][0])] += c
            else: raise NoSoportado("no lineal")
    # old = A^{-1} (new - b)
    inv = _inv(A)
    res = {}
    for i, o in enumerate(old):
        e = GP()
        for j, nv in enumerate(new): e = e + (GP.var(nv) - b[j]) * inv[i][j]
        res[o] = e
    return res


def _inv(A):
    n = len(A); M = [row[:] + [F(int(i == j)) for j in range(n)] for i, row in enumerate(A)]
    for c in range(n):
        p = next((r for r in range(c, n) if M[r][c] != 0), None)
        if p is None: raise NoSoportado("la transformación no es invertible")
        M[c], M[p] = M[p], M[c]
        pv = M[c][c]; M[c] = [x / pv for x in M[c]]
        for r in range(n):
            if r != c and M[r][c] != 0:
                f = M[r][c]; M[r] = [x - f * y for x, y in zip(M[r], M[c])]
    return [row[n:] for row in M]


def _resolver_monomial(old, new, defs):
    n = len(old); E = []; C = []
    for nv in new:
        g = defs[nv]
        if not g.is_mono(): raise NoSoportado("no monomial")
        (m, c), = g.t.items(); d = dict(m)
        E.append([d.get(o, F(0)) for o in old]); C.append(c)
    Ei = _inv(E)
    res = {}
    for i, o in enumerate(old):
        e = GP.const(1)
        for j, nv in enumerate(new):
            base = GP.var(nv) * (F(1) / C[j])
            e = e * base.mono_pow(Ei[i][j])
        res[o] = e
    return res


def preparar_mapa(old, new, mapa_txt, modo):
    """devuelve {old_i: Expr(new)} y descripción de los pasos de despeje"""
    pasos = []
    if modo == "directo":
        d = {o: _P(mapa_txt[o]) for o in old}
        pasos.append({"text": "Transformación dada", "latex": r"\quad ".join(f"{o} = {lat(d[o])}" for o in old)})
        return d, pasos
    defs = {nv: _gp(mapa_txt[nv]) for nv in new}
    pasos.append({"text": "Transformación dada", "latex": r"\quad ".join(f"{nv} = {lat(Expr.of(defs[nv]))}" for nv in new)})
    try: sol = _resolver_lineal(old, new, defs)
    except NoSoportado:
        sol = _resolver_monomial(old, new, defs)
    d = {o: Expr.of(sol[o]) for o in old}
    pasos.append({"text": "Se despejan las variables originales", "latex": r"\quad ".join(f"{o} = {lat(d[o])}" for o in old)})
    return d, pasos


def _subs_gp(g, sol):
    """GP en old → Expr en new"""
    e = Expr.of(g)
    for o, ex in sol.items(): e = e.subs(o, ex)
    return e


def _imagen_punto(p, old, new, mapa_txt, modo, sol):
    """imagen (u,v) del punto (x0,y0) del plano xy"""
    if modo == "inverso":
        env = {"x": float(p[0]), "y": float(p[1])}
        return tuple(compile_ast(normalize(parse(mapa_txt[nv])), old)(*[env[o] for o in old]) for nv in new)
    # directo: Newton sobre x(u,v)=x0, y(u,v)=y0 con varios puntos de partida
    import itertools
    for start in itertools.product([1.0, 3.0, 10.0, 30.0, 0.3], repeat=len(new)):
        u = list(start)
        try:
            for _ in range(60):
                env = dict(zip(new, u))
                r = [sol[o].eval(env) - float(p[i]) for i, o in enumerate(old)]
                if max(abs(v) for v in r) < 1e-11: return tuple(u)
                h = 1e-7; Jm = []
                for j, nv in enumerate(new):
                    e2 = dict(env); e2[nv] += h
                    Jm.append([(sol[o].eval(e2) - sol[o].eval(env)) / h for o in old])
                a, b, c_, d = Jm[0][0], Jm[1][0], Jm[0][1], Jm[1][1]
                det = a * d - b * c_
                if abs(det) < 1e-14: break
                du = (d * r[0] - b * r[1]) / det; dv = (-c_ * r[0] + a * r[1]) / det
                u = [u[0] - du, u[1] - dv]
        except (ValueError, ZeroDivisionError, OverflowError):
            continue
    raise NoSoportado("No se pudo hallar la imagen del punto interior en el plano nuevo")


def _f_nueva(f_txt, old, sol, mapa_txt, modo):
    """f(x(u,v), y(u,v)) como Expr: se sustituye en el AST (así (x−y)/(x+y) → u/v se simplifica solo)"""
    a = normalize(parse(f_txt))
    for o in old:
        rep = normalize(parse(mapa_txt[o])) if modo == "directo" else _gp_ast(sol[o].gp())
        a = ast_subs(a, o, rep)
    return from_ast(a)


def cambio_variables_doble(f_txt, curvas, new, mapa_txt, modo="inverso", orden="dydx", nombre="I", punto=None):
    """∬_R f(x,y) dA con la sustitución dada. curvas: ecuaciones de la frontera de R en x,y."""
    old = ["x", "y"]
    sol, pasos = preparar_mapa(old, new, mapa_txt, modo)
    M, J = jacobiano_matriz(old, new, sol)
    pasos.append({"text": "Jacobiano", "latex": r"\frac{\partial(x,y)}{\partial(%s,%s)} = %s = %s" % (new[0], new[1], _lat_matriz(M), lat(J))})
    # frontera transformada: se sustituye x,y en cada ecuación
    cur_new = []
    fronteras = []
    for t in curvas:
        l, r = t.split("=")
        g = _gp(f"({l})-({r})")
        e = _subs_gp(g, sol)
        eg = e.gp()                              # lanza NoSoportado si no es polinómico
        txt = eg.to_str() + "=0"
        cur_new.append(txt); fronteras.append((t, eg))
    pasos.append({"text": "Fronteras de la región en el plano " + "".join(new),
                  "latex": r"\quad ".join(r"\text{si } %s \Rightarrow %s = 0" % (t.replace("*", ""), eg.to_str(True)) for t, eg in fronteras)})
    # signo del jacobiano en el interior (muestra)
    fnew = _f_nueva(f_txt, old, sol, mapa_txt, modo)
    # |J|: se determina el signo con un punto interior del barrido
    from .region import barrido
    punto_n = _imagen_punto(punto, old, new, mapa_txt, modo, sol) if punto is not None else None
    piezas, _ = barrido(cur_new, new[0] if orden == "dydx" else new[1], par=tuple(new), punto=punto_n)
    pz = piezas[0]
    t0 = (pz.flo + pz.fhi) / 2
    s0 = (pz.inf.f(t0) + pz.sup.f(t0)) / 2
    env = {pz.inf.indep: t0, pz.inf.dep: s0}
    sg = J.eval(env)
    signo = 1 if sg > 0 else -1
    Jabs = J if signo > 0 else -J
    pasos.append({"text": "Elemento de área", "latex": r"dA = |J|\,d%s\,d%s = %s\,d%s\,d%s" % (new[0], new[1], lat(Jabs), new[0], new[1])})
    integrando = fnew * Jabs
    pasos.append({"text": "Integral en el plano nuevo (región sencilla)", "latex": r"%s = \iint f\,|J|\,d%s\,d%s,\quad f\,|J| = %s" % (nombre, new[0], new[1], lat(integrando))})
    forig = compile_ast(normalize(parse(f_txt)), ["x", "y"])
    solf = {o: (lambda *a, ex=ex: ex) for o, ex in sol.items()}
    def num(**kw):
        xs = {o: sol[o].eval(kw) for o in old}
        return forig(xs["x"], xs["y"]) * abs(J.eval(kw))
    r = integral_region(integrando, cur_new, orden, nombre=nombre, par=tuple(new), f_num=num, punto=punto_n)
    r["pasos"] = pasos + r["pasos"]
    r["jacobiano"] = J
    return r


def jacobiano(old, new, mapa_txt, modo="directo"):
    sol, pasos = preparar_mapa(old, new, mapa_txt, modo)
    M, J = jacobiano_matriz(old, new, sol)
    pasos.append({"text": "Matriz jacobiana y determinante", "latex": r"J = \frac{\partial(%s)}{\partial(%s)} = %s = %s" % (",".join(old), ",".join(new), _lat_matriz(M), lat(J))})
    return {"J": J, "pasos": pasos, "exacto": J}


def cambio_variables_caja(f_txt, old, new, mapa_txt, modo, niveles):
    """Integral triple con cambio de variables y límites dados en las variables nuevas (niveles: de la interna a la externa)."""
    sol, pasos = preparar_mapa(old, new, mapa_txt, modo)
    M, J = jacobiano_matriz(old, new, sol)
    pasos.append({"text": "Jacobiano", "latex": r"\frac{\partial(%s)}{\partial(%s)} = %s = %s" % (",".join(old), ",".join(new), _lat_matriz(M), lat(J))})
    fnew = _f_nueva(f_txt, old, sol, mapa_txt, modo)
    # signo de J en el centro de la caja
    env = {}
    for lv in niveles:
        lo, hi = lv["lo"].eval(env), lv["hi"].eval(env)
        env[lv["var"]] = (lo + hi) / 2
    # los límites pueden depender de las variables externas: se recorren de la externa a la interna
    env = {}
    for lv in reversed(niveles):
        lo, hi = lv["lo"].eval(env), lv["hi"].eval(env)
        env[lv["var"]] = (lo + hi) / 2
    Jabs = J if J.eval(env) > 0 else -J
    pasos.append({"text": "Elemento de volumen", "latex": r"dV = |J|\,d%s = %s\,d%s" % ("\\,d".join(new), lat(Jabs), "\\,d".join(new))})
    integrando = fnew * Jabs
    forig = compile_ast(normalize(parse(f_txt)), list(old))
    ext_first = [lv["var"] for lv in reversed(niveles)]
    def num(*a):
        kw = dict(zip(ext_first, a))
        xs = [sol[o].eval(kw) for o in old]
        return forig(*xs) * abs(J.eval(kw))
    r = integrar(integrando, niveles, f_num=num, nombre="I")
    r["pasos"] = pasos + r["pasos"]; r["jacobiano"] = J
    return r
