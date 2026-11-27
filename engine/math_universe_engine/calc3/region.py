"""Barrido de una región plana limitada por curvas → piezas  xlo ≤ t ≤ xhi,  inferior(t) ≤ s ≤ superior(t)."""
import math
from fractions import Fraction as F
from ..arith import evaluate as arith_eval
from .cas3 import GP, Expr, NoSoportado, raiz_gp
from .curvas import ramas_de, _raices, snap, Rama, _prep


def _fl(v): return v.eval({}) if isinstance(v, GP) else float(v)


class Pieza:
    def __init__(self, lo, hi, inf, sup, flo, fhi):
        self.lo, self.hi = lo, hi          # extremos (Fraction o float)
        self.inf, self.sup = inf, sup      # Rama
        self.flo, self.fhi = _fl(lo), _fl(hi)


def _def(r, x):
    try:
        v = r.f(x)
        return None if (isinstance(v, complex) or v != v or abs(v) == float("inf")) else v
    except Exception:
        return None


def barrido(curvas, indep, ventana=(-40.0, 40.0), par=("x", "y"), punto=None):
    """curvas: lista de textos. indep='x' → piezas en x (orden dy dx); indep='y' → piezas en y (orden dx dy)."""
    ramas, paredes = [], []
    for t in curvas:
        for r in ramas_de(t, indep, par):
            if isinstance(r, tuple):
                paredes.append((float(arith_eval(r[1])), F(arith_eval(r[1])), r[2]))
            else:
                ramas.append(_prep(r))
    if not ramas: raise NoSoportado("Se necesita al menos una curva y=f(x) o x=g(y)")
    a0, b0 = ventana
    crit = []                                   # (valor float, exacto|None)
    for w in paredes: crit.append((w[0], w[1]))
    n = len(ramas)
    for i in range(n):
        # extremos del dominio de cada rama
        _dominio(ramas[i], a0, b0, crit)
        for j in range(i + 1, n):
            h = lambda t, p=ramas[i], q=ramas[j]: p.f(t) - q.f(t)
            for x in _raices(h, a0, b0):
                crit.append((x, _exacto(x, ramas[i], ramas[j])))
    # eje: ordenar y deduplicar
    crit.sort(key=lambda c: c[0])
    xs = []
    for v, ex in crit:
        if xs and abs(v - xs[-1][0]) < 1e-9 * (1 + abs(v)):
            if xs[-1][1] is None and ex is not None: xs[-1] = (xs[-1][0], ex)
            continue
        xs.append((v, ex))
    if len(xs) < 2: raise NoSoportado("Las curvas no encierran una región acotada")
    wallset = [w[0] for w in paredes]
    # tiras
    tiras = []
    for k in range(len(xs) - 1):
        m = (xs[k][0] + xs[k + 1][0]) / 2
        vals = []
        for r in ramas:
            v = _def(r, m)
            if v is not None: vals.append((v, r))
        vals.sort(key=lambda p: p[0])
        for (va, ra), (vb, rb) in zip(vals, vals[1:]):
            if vb - va > 1e-9: tiras.append({"k": k, "a": ra, "b": rb, "id": len(tiras)})
    # caras: unión por continuidad
    padre = list(range(len(tiras)))
    def find(i):
        while padre[i] != i: padre[i] = padre[padre[i]]; i = padre[i]
        return i
    def pared(x): return any(abs(x - w) < 1e-9 for w in wallset)
    def extent(t, x):
        va, vb = _def(t["a"], x), _def(t["b"], x)
        return (va, vb)
    for p in tiras:
        for q in tiras:
            if q["k"] == p["k"] + 1:
                xc = xs[q["k"]][0]
                if pared(xc): continue
                pa, pb = extent(p, xc); qa, qb = extent(q, xc)
                if None in (pa, pb, qa, qb): continue
                if abs(pa - qa) < 1e-7 and abs(pb - qb) < 1e-7 and pb - pa > 1e-7:
                    padre[find(p["id"])] = find(q["id"])
    caras = {}
    for t in tiras: caras.setdefault(find(t["id"]), []).append(t)
    acotadas = []
    for tl in caras.values():
        tl.sort(key=lambda t: t["k"])
        ok_i = _cerrada(tl[0], xs[tl[0]["k"]][0], pared, extent)
        ok_d = _cerrada(tl[-1], xs[tl[-1]["k"] + 1][0], pared, extent)
        if ok_i and ok_d: acotadas.append(tl)
    if not acotadas: raise NoSoportado("Las curvas no encierran una región acotada")
    if punto is not None:
        pi_, pd_ = punto[par.index(indep)], punto[1 - par.index(indep)]
        sel = []
        for tl in acotadas:
            for t in tl:
                if xs[t["k"]][0] <= pi_ <= xs[t["k"] + 1][0]:
                    va, vb = _def(t["a"], pi_), _def(t["b"], pi_)
                    if va is not None and vb is not None and va - 1e-12 <= pd_ <= vb + 1e-12:
                        sel.append(tl); break
        if not sel: raise NoSoportado("El punto indicado no está dentro de ninguna región acotada por las curvas")
        acotadas = sel
    acotadas.sort(key=lambda tl: xs[tl[0]["k"]][0])
    piezas = []
    for tl in acotadas:
        for t in tl:
            lo, hi = xs[t["k"]][1], xs[t["k"] + 1][1]
            lo = lo if lo is not None else xs[t["k"]][0]
            hi = hi if hi is not None else xs[t["k"] + 1][0]
            if piezas and piezas[-1].inf is t["a"] and piezas[-1].sup is t["b"] and piezas[-1].flo <= _fl(lo) and abs(piezas[-1].fhi - _fl(lo)) < 1e-9:
                piezas[-1].hi = hi; piezas[-1].fhi = _fl(hi)
            else:
                piezas.append(Pieza(lo, hi, t["a"], t["b"], lo, hi))
    return piezas, len(acotadas)


def _cerrada(t, x, pared, extent):
    if pared(x): return True
    a, b = extent(t, x)
    return a is not None and b is not None and abs(a - b) < 1e-7


def _dominio(r, a0, b0, crit):
    """si la rama deja de estar definida (p. ej. sqrt) añade el extremo del dominio"""
    n = 2000; prev = _def(r, a0)
    for i in range(1, n + 1):
        x = a0 + (b0 - a0) * i / n
        cur = _def(r, x)
        if (prev is None) != (cur is None):
            lo, hi = x - (b0 - a0) / n, x
            for _ in range(100):
                md = (lo + hi) / 2
                if (_def(r, md) is None) == (prev is None): lo = md
                else: hi = md
            e = lo if prev is not None else hi
            e = hi if prev is None else lo
            ex = snap(e, lambda fr: True) if _def(r, float(snap(e, lambda fr: True))) is not None or True else e
            crit.append((float(e), ex if isinstance(ex, F) else None))
        prev = cur


def _candidatos(x):
    """x como racional o q·√N (N libre de cuadrados) → lista de GP/Fraction candidatos"""
    out = []
    fr = F(x).limit_denominator(2000)
    if abs(float(fr) - x) <= 1e-11 * (1 + abs(x)): out.append(fr)
    x2 = F(x * x).limit_denominator(4000)
    if x2 > 0 and abs(float(x2) - x * x) <= 1e-10 * (1 + x * x):
        g = raiz_gp(x2)
        out.append(g if x >= 0 else -g)
    return out


def _exacto(x, p, q):
    """Valor exacto (Fraction o GP con √N) si p(x)=q(x) se cumple exactamente; si no None."""
    for c in _candidatos(x):
        if p.ex is not None and q.ex is not None:
            try:
                e = (p.ex - q.ex).subs(p.indep, c if isinstance(c, GP) else GP.const(c)).gp()
                if e.is_zero(): return c
            except Exception:
                pass
        else:
            cf = float(c) if not isinstance(c, GP) else c.eval({})
            try:
                if abs(p.f(cf) - q.f(cf)) < 1e-12: return c
            except Exception: pass
    return None
