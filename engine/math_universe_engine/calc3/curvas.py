"""Regiones planas limitadas por curvas: ramas explícitas, intersecciones exactas y barrido en x o en y."""
import math
from fractions import Fraction as F
from ..parser import parse
from ..ast_tools import normalize
from .cas3 import GP, Expr, NoSoportado, from_ast, mk_pow
from .numerico import compile_ast


class Rama:
    """Una rama explícita  dep = f(indep)  de una curva."""
    def __init__(self, dep, indep, ex, texto):
        self.dep, self.indep, self.ex, self.texto = dep, indep, ex, texto
        self.num = None
        self.f = None  # callable numérico

    def valor(self, t): return self.f(t)


def _ast(s): return normalize(parse(s))


def _gp_or_none(ast):
    try:
        e = from_ast(ast)
        return e if e.is_gp() else None
    except NoSoportado:
        return None
    except Exception:
        return None


def ramas_de(texto, indep, par=("x", "y")):
    """Ramas explícitas dep=f(indep) de una curva (indep='x' → y=f(x); indep='y' → x=g(y)).
    Cada rama se valida contra la ecuación ORIGINAL (así x=y²/4 no incluye y<0 cuando la curva era y=2√x)."""
    from ..ast_tools import free_symbols
    dep = par[1] if indep == par[0] else par[0]
    t = texto.replace("−", "-")
    if t.count("=") != 1: raise NoSoportado(f"La curva «{texto}» debe tener un único signo =")
    l, r = [q.strip() for q in t.split("=")]
    la, ra = _ast(l), _ast(r)
    fl, fr = free_symbols(la), free_symbols(ra)
    resid = compile_ast(("bin", "-", la, ra), list(par))
    def valida(rama):
        f0 = rama.f
        def f(tt):
            v = f0(tt)
            if isinstance(v, complex): raise ValueError
            args = (tt, v) if indep == par[0] else (v, tt)
            if abs(resid(*args)) > 1e-8 * (1 + abs(v) + abs(tt)): raise ValueError("fuera de la curva")
            return v
        rama.f = f
        return rama
    # pared (x=c al barrer en x, y=c al barrer en y)
    if la == ("sym", indep) and not fr: return [("pared", ra, texto)]
    if ra == ("sym", indep) and not fl: return [("pared", la, texto)]
    # forma explícita dep = f(indep)
    if la == ("sym", dep) and dep not in fr: return [_mk(dep, indep, ra, texto)]
    if ra == ("sym", dep) and dep not in fl: return [_mk(dep, indep, la, texto)]
    g = _gp_or_none(("bin", "-", la, ra))
    if g is None: raise NoSoportado(f"No se pudo despejar la curva «{texto}»: escríbala como y=f(x) o x=g(y)")
    g = _sin_monomio_comun(g.gp())
    if not g.has(dep):                                   # solo depende de la variable de barrido → paredes verticales
        ci = g.coef_in(indep)
        if set(ci) == {F(1), F(0)} and ci[F(1)].is_const() and ci[F(0)].is_const():
            return [("pared", ("num", -ci[F(0)].cval() / ci[F(1)].cval()), texto)]
        if set(ci) == {F(1)}: return [("pared", ("num", F(0)), texto)]
        if len(ci) == 2 and F(0) in ci and ci[[e for e in ci if e != 0][0]].is_const() and ci[F(0)].is_const():
            a = [e for e in ci if e != 0][0]
            k = -ci[F(0)].cval() / ci[a].cval()
            if k > 0:
                try:
                    rt = GP.const(k).mono_pow(F(1) / a).cval()
                    if a.denominator == 1 and int(a) % 2 == 0:
                        return [("pared", ("num", rt), texto), ("pared", ("num", -rt), texto)]
                    return [("pared", ("num", rt), texto)]
                except Exception: pass
        raise NoSoportado(f"No se pudo interpretar la frontera «{texto}»")
    cs = g.coef_in(dep)
    exps = sorted(cs)
    out = []
    # una sola potencia de dep:  c·dep^a = -resto(indep)
    if len(exps) == 2 and F(0) in exps:
        a = [e for e in exps if e != 0][0]; c = cs[a]; resto = cs[F(0)]
        if c.is_mono():
            rhs = -(resto * c.inv())
            signos = [1] if a.denominator == 1 and int(a) % 2 == 1 else [1, -1]
            for sg in signos:
                try:
                    if a == 1: ex = Expr.of(rhs)
                    else:
                        if not rhs.is_mono(): raise NoSoportado("")
                        ex = Expr.of(rhs.mono_pow(F(1) / a))
                    if sg == -1: ex = -ex
                    rm = Rama(dep, indep, ex, f"{dep}={ex.to_str()}")
                    rm.f = (lambda tt, e=ex, v=indep: e.eval({v: tt})); rm.ast = None
                    out.append(valida(rm))
                except NoSoportado:
                    if a == 2 or a == F(2):
                        sq = ("call", "sqrt", [_gp_ast(rhs)])
                        ast = sq if sg == 1 else ("neg", sq)
                        rm = Rama(dep, indep, None, f"{dep}={'' if sg == 1 else '-'}sqrt({rhs.to_str()})")
                        rm.f = compile_ast(ast, [indep]); rm.ast = ast
                        out.append(valida(rm))
                    else: raise
            return out
    # polinomio de grado 1 en dep (varios términos en indep): dep = -resto/c
    if exps == [F(0), F(1)] or exps == [F(1)]:
        c = cs[F(1)]
        if c.is_mono():
            ex = Expr.of(-(cs.get(F(0), GP()) * c.inv()))
            rm = Rama(dep, indep, ex, f"{dep}={ex.to_str()}"); rm.f = (lambda tt, e=ex, v=indep: e.eval({v: tt})); rm.ast = None
            return [rm]
    # cuadrática en dep:  a·d² + b·d + c = 0
    if set(exps) <= {F(0), F(1), F(2)} and F(2) in cs:
        A, B, C = cs[F(2)], cs.get(F(1), GP()), cs.get(F(0), GP())
        disc = ("bin", "-", ("bin", "*", _gp_ast(B), _gp_ast(B)), ("bin", "*", ("num", F(4)), ("bin", "*", _gp_ast(A), _gp_ast(C))))
        for sg in (1, -1):
            ast = ("bin", "/", ("bin", "+" if sg == 1 else "-", ("neg", _gp_ast(B)), ("call", "sqrt", [disc])), ("bin", "*", ("num", F(2)), _gp_ast(A)))
            rm = Rama(dep, indep, None, f"{dep}=(-b{'+' if sg == 1 else '-'}√Δ)/2a")
            rm.f = compile_ast(ast, [indep]); rm.ast = ast
            out.append(valida(rm))
        return out
    raise NoSoportado(f"No se pudo despejar la curva «{texto}»: escríbala como y=f(x) o x=g(y)")


def _sin_monomio_comun(g):
    """divide por el máximo monomio común (válido en el primer cuadrante / región positiva)"""
    if len(g.t) < 2: return g
    mins = None
    for m in g.t:
        d = dict(m)
        mins = d if mins is None else {k: min(mins.get(k, F(0)), d.get(k, F(0))) for k in set(mins) | set(d)}
    mins = {k: v for k, v in mins.items() if v != 0}
    if not mins: return g
    return g * GP({tuple((k, -v) for k, v in sorted(mins.items())): F(1)})


def _gp_ast(g):
    """GP → AST (para el evaluador numérico)"""
    terms = []
    for m, c in g.t.items():
        t = ("num", c)
        for n, e in m:
            b = ("sym", n)
            t = ("bin", "*", t, ("bin", "^", b, ("num", e)) if e != 1 else b)
        terms.append(t)
    if not terms: return ("num", F(0))
    r = terms[0]
    for t in terms[1:]: r = ("bin", "+", r, t)
    return r


def _despejar2(g, dep):
    cs = g.coef_in(dep)
    return _gp_ast(-(cs.get(F(0), GP())) * cs[F(2)].inv())


def _pasar(p): return _gp_ast(p.gp())


def _raiz(p):
    """sqrt de Expr GP monomio"""
    g = p.gp()
    if g.is_mono(): return Expr.of(g.mono_pow(F(1, 2)))
    raise NoSoportado("raíz de un polinomio no monomio")


def _mk(dep, indep, ast, texto):
    try: e = from_ast(ast)
    except Exception: e = None
    r = Rama(dep, indep, e, texto)
    r.f = compile_ast(ast, [indep])
    r.ast = ast
    return r


def _numerica(dep, indep, ast, texto, resto=None, neg=False):
    r = Rama(dep, indep, None, texto)
    r.f = compile_ast(ast, [indep]); r.ast = ast
    return r


def _prep(r):
    if r.f is None and r.ex is not None:
        r.f = lambda t, e=r.ex, v=r.indep: e.eval({v: t})
    return r


# ---------------------------------------------------------------- intersecciones
def _raices(h, a, b, n=4000):
    """raíces reales de h en [a,b] por barrido + bisección + Newton"""
    xs = [a + (b - a) * i / n for i in range(n + 1)]
    vs = []
    for x in xs:
        try: vs.append(h(x))
        except Exception: vs.append(None)
    out = []
    for i in range(n):
        v0, v1 = vs[i], vs[i + 1]
        if v0 is None or v1 is None: continue
        if v0 == 0: out.append(xs[i]); continue
        if v0 * v1 < 0:
            lo, hi = xs[i], xs[i + 1]
            for _ in range(100):
                md = (lo + hi) / 2
                try: vm = h(md)
                except Exception: break
                if vm == 0: lo = hi = md; break
                if vm * h(lo) < 0: hi = md
                else: lo = md
            out.append((lo + hi) / 2)
        elif abs(v0) < 1e-14 and abs(v1) > 0: pass
    if vs[-1] == 0: out.append(xs[-1])
    # raíces dobles (tangencia): mínimos de |h|
    for i in range(1, n):
        if vs[i - 1] is None or vs[i] is None or vs[i + 1] is None: continue
        if abs(vs[i]) < abs(vs[i - 1]) and abs(vs[i]) <= abs(vs[i + 1]) and abs(vs[i]) < 1e-3 * (1 + abs(b - a)):
            lo, hi = xs[i - 1], xs[i + 1]
            for _ in range(80):
                m1, m2 = lo + (hi - lo) / 3, hi - (hi - lo) / 3
                try:
                    if abs(h(m1)) < abs(h(m2)): hi = m2
                    else: lo = m1
                except Exception: break
            x0 = (lo + hi) / 2
            try:
                if abs(h(x0)) < 1e-9 and not any(abs(x0 - o) < 1e-6 for o in out): out.append(x0)
            except Exception: pass
    out.sort()
    ded = []
    for o in out:
        if not ded or abs(o - ded[-1]) > 1e-9 * (1 + abs(o)): ded.append(o)
    return ded


def fraccion_exacta(x, ramas_cero=None, maxden=2000):
    """Intenta reconocer x como racional p/q y lo devuelve como Fraction (o None)."""
    fr = F(x).limit_denominator(maxden)
    return fr if abs(float(fr) - x) < 1e-11 * (1 + abs(x)) else None


def snap(x, comprobar):
    """Racional exacto si 'comprobar(Fraction)' verifica con aritmética exacta; si no, el float."""
    fr = fraccion_exacta(x)
    if fr is not None:
        try:
            if comprobar(fr): return fr
        except Exception:
            pass
    return x
