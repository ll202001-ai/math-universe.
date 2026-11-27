"""Áreas, volúmenes, masa y centro de masa de láminas, integrales dobles sobre regiones limitadas por curvas."""
from fractions import Fraction as F
from .cas3 import GP, Expr, NoSoportado, NoPrimitiva, from_ast
from .region import barrido
from .iterada import integrar, lat, lat_integral, _fmt_num
from .numerico import integral as quad
from ..parser import parse
from ..ast_tools import normalize


def P(s): return from_ast(normalize(parse(s)))


def _ex(x):
    if isinstance(x, Expr): return x
    if isinstance(x, GP): return Expr.of(x)
    if isinstance(x, F): return Expr.of(GP.const(x))
    return None


class NumBound:
    """límite no exacto: se evalúa numéricamente"""
    def __init__(self, f, txt): self.f, self.txt = f, txt
    def is_gp(self): return False
    def eval(self, env): return self.f(*env.values()) if env else self.f()
    def to_str(self, latex=False): return self.txt


def _niveles(pieza, indep):
    dep = "y" if indep == "x" else "x"
    lo, hi = _ex(pieza.lo), _ex(pieza.hi)
    inf, sup = pieza.inf.ex, pieza.sup.ex
    exacto = all(v is not None for v in (lo, hi, inf, sup))
    return dep, lo, hi, inf, sup, exacto


def integral_region(f, curvas, orden="dydx", nombre="I", f_txt=None, par=("x", "y"), f_num=None, punto=None):
    """f: Expr. orden 'dydx' (barrido en par[0]) o 'dxdy' (barrido en par[1]). Devuelve dict con pasos."""
    indep = par[0] if orden == "dydx" else par[1]
    dep = par[1] if indep == par[0] else par[0]
    piezas, ncaras = barrido(curvas, indep, par=par, punto=punto)
    pasos = []
    tot = Expr(); tot_ok = True; aprox = 0.0; cuad = 0.0; err = 0.0
    planes = []
    verifs = []
    for k, pz in enumerate(piezas):
        dep_, lo, hi, inf, sup, exacto = _niveles(pz, indep)
        titulo = f"Región {k + 1} de {len(piezas)}: " if len(piezas) > 1 else ""
        if exacto:
            niv = [{"var": dep, "lo": inf, "hi": sup}, {"var": indep, "lo": lo, "hi": hi}]
            r = integrar(f, niv, nombre=f"{nombre}_{k + 1}" if len(piezas) > 1 else nombre, f_num=_adapt(f_num, indep, dep))
            planes.append(lat_integral(niv, lat(f)))
            sub = r["pasos"]
            if len(piezas) > 1: sub = [dict(p, text=titulo + p["text"]) if i == 0 else p for i, p in enumerate(sub)]
            pasos += sub
            if r["exacto"] is None: tot_ok = False
            else: tot = tot + r["exacto"]
            aprox += r["aprox"]; verifs.append(r["verificacion"])
            cuad += r["cuadratura"]; err += r["err_cuadratura"]
        else:
            tot_ok = False
            val, e = _num_pieza(f, pz, dep, indep, f_num)
            aprox += val; cuad += val; err += e; verifs.append("passed" if e < 1e-7 else "not_possible")
            planes.append(f"\\int_{{{pz.flo:.6g}}}^{{{pz.fhi:.6g}}}\\int_{{{pz.inf.texto}}}^{{{pz.sup.texto}}} {lat(f)}\\,d{dep}\\,d{indep}")
            pasos.append({"text": titulo + "Límites no polinómicos: se evalúa por cuadratura numérica", "latex": f"{nombre}_{k + 1} \\approx {_fmt_num(val)}"})
    res = {"planteamiento": " + ".join(planes), "pasos": pasos, "piezas": piezas, "caras": ncaras, "avisos": []}
    if ncaras > 1 and punto is None:
        res["avisos"].append(f"Las curvas encierran {ncaras} regiones acotadas y se sumaron todas. Si usted se refiere a una sola, indique un punto dentro de ella.")
    res["aprox"] = aprox; res["cuadratura"] = cuad
    if tot_ok:
        res["exacto"] = tot
        ap = tot.eval({}); res["aprox"] = ap
        res["verificacion"] = "passed" if all(v == "passed" for v in verifs) and abs(ap - cuad) <= 1e-7 * (1 + abs(ap)) + 10 * err else "failed"
        if len(piezas) > 1:
            pasos.append({"text": "Se suman las integrales de cada región", "latex": f"{nombre} = {lat(tot)} \\approx {_fmt_num(ap)}"})
    else:
        res["exacto"] = None
        res["verificacion"] = "passed" if all(v == "passed" for v in verifs) else "not_possible"
    return res


def _adapt(f_num, indep, dep):
    """f_num(**{var: valor}) → función posicional (indep, dep) para la cuadratura (la más externa primero)"""
    if f_num is None: return None
    return lambda a, b: f_num(**{indep: a, dep: b})


def _num_pieza(f, pz, dep, indep, f_num=None):
    fnum = _adapt(f_num, indep, dep) or (lambda a, b, fe=f: fe.eval({indep: a, dep: b}))
    lo_f = lambda t, r=pz.inf: r.f(t)
    hi_f = lambda t, r=pz.sup: r.f(t)
    return quad(fnum, [(lo_f, hi_f), (pz.flo, pz.fhi)])


def descripcion_region(curvas, orden):
    indep = "x" if orden == "dydx" else "y"
    piezas, n = barrido(curvas, indep)
    puntos = []
    for pz in piezas:
        for v in (pz.lo, pz.hi):
            if v not in [p for p in puntos]: puntos.append(v)
    return piezas, puntos


# ------------------------------------------------------------- casos de uso
def area(curvas, orden="dydx", punto=None):
    r = integral_region(Expr.of(1), curvas, orden, nombre="A", punto=punto)
    return r


def volumen(z, curvas, orden="dydx", punto=None):
    return integral_region(P(z) if isinstance(z, str) else z, curvas, orden, nombre="V", punto=punto)


def _cociente(a, b):
    """a/b exacto si b es un monomio constante (racional, π, √N); si no, None"""
    try:
        ga, gb = a.gp(), b.gp()
        if gb.is_mono(): return Expr.of(ga * gb.inv())
    except Exception:
        pass
    return None


def masa_centroide(delta, curvas, orden="dydx", punto=None):
    d = P(delta) if isinstance(delta, str) else delta
    X, Y = Expr.of(GP.var("x")), Expr.of(GP.var("y"))
    rm = integral_region(d, curvas, orden, nombre="m", punto=punto)
    rMy = integral_region(X * d, curvas, orden, nombre="M_y", punto=punto)
    rMx = integral_region(Y * d, curvas, orden, nombre="M_x", punto=punto)
    out = {"m": rm, "My": rMy, "Mx": rMx}
    m, My, Mx = rm["aprox"], rMy["aprox"], rMx["aprox"]
    out["xbar_aprox"], out["ybar_aprox"] = My / m, Mx / m
    if rm["exacto"] is not None and rMy["exacto"] is not None and rMx["exacto"] is not None:
        out["xbar"] = _cociente(rMy["exacto"], rm["exacto"])
        out["ybar"] = _cociente(rMx["exacto"], rm["exacto"])
    else:
        out["xbar"] = out["ybar"] = None
    return out


# ------------------------------------------------------------- sólido entre dos superficies sobre una región D
def triple_sobre_region(f, zinf, zsup, curvas, orden="dydx", punto=None, nombre="V", proyeccion_auto=True):
    """∭ f dV sobre {(x,y)∈D, zinf ≤ z ≤ zsup}.  D la limitan 'curvas' (+ la proyección de zinf = zsup si proyeccion_auto)."""
    from .iterada import lat_integral
    from .numerico import integral as q1
    fe = f if isinstance(f, Expr) else P(f)
    zi, zs = P(zinf), P(zsup)
    curvas = list(curvas)
    pasos = []
    base_curvas = list(curvas)
    dif = zi - zs
    constante = all(not (isinstance(a, str) and a in ("x", "y")) for a in [])  # placeholder, se refina abajo
    try:
        constante = dif.eval({"x": 0.3, "y": 0.7}) == dif.eval({"x": 1.1, "y": -0.4}) == dif.eval({"x": -0.9, "y": 2.3})
    except Exception:
        constante = False
    if proyeccion_auto and not constante:
        curvas.append(f"({zinf})-({zsup})=0")
    from .integra import integrate
    try:
        Fz = integrate(fe, "z")
        G = Fz.subs("z", zs) - Fz.subs("z", zi)
    except (NoPrimitiva, NoSoportado) as e:
        raise NoSoportado("La integral en z no tiene primitiva elemental: " + str(e))
    pasos.append({"text": "Planteamiento: se integra primero en z (entre las dos superficies) y luego sobre la región D del plano xy",
                  "latex": nombre + r" = \iint_D \int_{%s}^{%s} %s\,dz\,dA" % (lat(zi), lat(zs), lat(fe))})
    pasos.append({"text": "Integral interna (respecto a z)", "latex": r"\int_{%s}^{%s} %s\,dz = \left[%s\right]_{%s}^{%s} = %s" % (lat(zi), lat(zs), lat(fe), lat(Fz), lat(zi), lat(zs), lat(G))})
    from .numerico import compile_ast
    fn_f = compile_ast(normalize(parse(f if isinstance(f, str) else "1")), ["x", "y", "z"]) if isinstance(f, str) else (lambda x, y, z, e=fe: e.eval({"x": x, "y": y, "z": z}))
    def fnum(**kw):
        x, y = kw["x"], kw["y"]
        a, b = zi.eval(kw), zs.eval(kw)
        return q1(lambda z: fn_f(x, y, z), [(a, b)])[0]
    r = None
    if len(base_curvas) >= 2 and len(curvas) > len(base_curvas):
        # si las curvas dadas ya cierran una región, la proyección extra solo estorba
        try:
            r = integral_region(G, base_curvas, orden, nombre=nombre, f_num=fnum, punto=punto)
            curvas = base_curvas
        except Exception:
            r = None
    if r is None:
        r = integral_region(G, curvas, orden, nombre=nombre, f_num=fnum, punto=punto)
    r["pasos"] = pasos + r["pasos"]
    r["curvas_D"] = curvas
    return r
