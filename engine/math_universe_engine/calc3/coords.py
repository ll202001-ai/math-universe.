"""Coordenadas polares, cilíndricas y esféricas: integrales en el sistema que conviene, con su jacobiano."""
import math
from fractions import Fraction as F
from ..parser import parse
from ..ast_tools import normalize, subs as ast_subs
from .cas3 import Expr, GP, NoSoportado, from_ast, pitag
from .iterada import integrar, lat
from .numerico import compile_ast

SIS = {
    "polares": {"vars": ("r", "theta"), "x": "r*cos(theta)", "y": "r*sin(theta)", "J": "r", "nombre": "polares",
                "lat": [r"x = r\cos\theta", r"y = r\sin\theta"], "dV": r"dA = r\,dr\,d\theta"},
    "cilindricas": {"vars": ("r", "theta", "z"), "x": "r*cos(theta)", "y": "r*sin(theta)", "z": "z", "J": "r",
                    "nombre": "cilíndricas", "lat": [r"x = r\cos\theta", r"y = r\sin\theta", "z = z"], "dV": r"dV = r\,dz\,dr\,d\theta"},
    "esfericas": {"vars": ("rho", "phi", "theta"), "x": "rho*sin(phi)*cos(theta)", "y": "rho*sin(phi)*sin(theta)", "z": "rho*cos(phi)",
                  "J": "rho^2*sin(phi)", "nombre": "esféricas",
                  "lat": [r"x = \rho\sin\varphi\cos\theta", r"y = \rho\sin\varphi\sin\theta", r"z = \rho\cos\varphi"],
                  "dV": r"dV = \rho^{2}\sin\varphi\,d\rho\,d\varphi\,d\theta"},
}


def _P(s): return normalize(parse(s))


def _terms(n, out):
    if n[0] == "bin" and n[1] == "+":
        _terms(n[2], out); _terms(n[3], out)
    else: out.append(n)


def _sq(sym): return ("bin", "^", ("sym", sym), ("num", F(2)))


def _pre(n, tipo):
    """x²+y²(+z²) → expresión en las nuevas variables antes de sustituir (así sen²+cos² no estorba)"""
    k = n[0]
    if k == "bin" and n[1] == "+":
        ts = []; _terms(n, ts)
        names = {"x": _sq("x"), "y": _sq("y"), "z": _sq("z")}
        has = {s: (names[s] in ts) for s in names}
        if tipo == "esfericas" and all(has.values()):
            rest = [t for t in ts if t not in names.values()]
            new = [("bin", "^", ("sym", "rho"), ("num", F(2)))] + [_pre(t, tipo) for t in rest]
        elif tipo in ("cilindricas", "polares") and has["x"] and has["y"]:
            rest = [t for t in ts if t not in (names["x"], names["y"])]
            new = [("bin", "^", ("sym", "r"), ("num", F(2)))] + [_pre(t, tipo) for t in rest]
        elif tipo == "esfericas" and has["x"] and has["y"]:
            rest = [t for t in ts if t not in (names["x"], names["y"])]
            new = [("bin", "*", ("bin", "^", ("sym", "rho"), ("num", F(2))), ("bin", "^", ("call", "sin", [("sym", "phi")]), ("num", F(2))))] + [_pre(t, tipo) for t in rest]
        else:
            return ("bin", "+", _pre(n[2], tipo), _pre(n[3], tipo))
        r = new[0]
        for t in new[1:]: r = ("bin", "+", r, t)
        return r
    if k == "bin": return ("bin", n[1], _pre(n[2], tipo), _pre(n[3], tipo))
    if k == "neg": return ("neg", _pre(n[1], tipo))
    if k == "call": return ("call", n[1], [_pre(a, tipo) for a in n[2]])
    return n


def a_nuevas(f_txt, tipo):
    """AST de f(x,y,z) reescrito en las variables del sistema (sin jacobiano)"""
    s = SIS[tipo]; a = _pre(_P(f_txt), tipo)
    for c in ("x", "y", "z"):
        if c in s: a = ast_subs(a, c, _P(s[c]))
    return a


def integral(f_txt, tipo, niveles, nombre="I"):
    """niveles: [(var, lo, hi)] de la más interna a la más externa (textos en las variables del sistema)."""
    s = SIS[tipo]
    an = a_nuevas(f_txt, tipo)
    J = from_ast(_P(s["J"]))
    fn = pitag(from_ast(an) * J)
    niv = [{"var": v, "lo": from_ast(_P(lo)), "hi": from_ast(_P(hi))} for v, lo, hi in niveles]
    # verificación independiente: se evalúa el integrando ORIGINAL en x,y,z y se multiplica por el jacobiano numérico
    orig = compile_ast(_P(f_txt), ["x", "y", "z"])
    ext_first = [lv["var"] for lv in reversed(niv)]
    def num(*a, s=s):
        env = dict(zip(ext_first, a))
        v = {n: env[n] for n in s["vars"]}
        xx = _ev(s["x"], v); yy = _ev(s["y"], v); zz = _ev(s["z"], v) if "z" in s else 0.0
        return orig(xx, yy, zz) * _ev(s["J"], v)
    r = integrar(fn, niv, f_num=num, nombre=nombre)
    cab = [{"text": f"Cambio a coordenadas {s['nombre']}", "latex": r"\quad ".join(s["lat"]) + r",\quad " + s["dV"]},
           {"text": "El integrando se escribe en las nuevas variables y se multiplica por el jacobiano", "latex": lat(fn)}]
    r["pasos"] = cab + r["pasos"]
    return r


_CC = {}


def _ev(txt, env):
    if txt not in _CC: _CC[txt] = compile_ast(_P(txt), list(SIS_VARS))
    return _CC[txt](*[env.get(n, 0.0) for n in SIS_VARS])


SIS_VARS = ("r", "theta", "z", "rho", "phi")
