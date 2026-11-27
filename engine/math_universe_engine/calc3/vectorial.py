"""Cálculo vectorial: gradiente, divergencia, rotacional, laplaciano, campos conservativos (función potencial),
integrales de línea (trabajo / circulación / longitud) con contraste por el teorema de Green cuando la curva es cerrada y plana.
Todo exacto con cas3 y verificado numéricamente de forma independiente (diferencias finitas / cuadratura)."""
import math
import random
from fractions import Fraction as F
from ..errors import InvalidRequest, VerificationFailed
from ..parser import parse
from ..ast_tools import normalize, subs as ast_subs, to_str as ast_str
from .cas3 import from_ast, Expr, NoSoportado, NoPrimitiva
from .numerico import compile_ast
from . import integra
from .iterada import integrar, _fmt_num


def _A(s): return normalize(parse(s))


def _E(s): return from_ast(_A(s))


def derivar(s, v):
    return _E(s).deriv(v)


def _chk_deriv(s, v, d, vs):
    """comprueba la derivada con diferencias finitas centradas en puntos pseudoaleatorios"""
    f = compile_ast(_A(s), vs); g = compile_ast(_A(d.to_str()), vs)
    rnd = random.Random(7); ok = 0; tot = 0
    for _ in range(8):
        p = [rnd.uniform(0.3, 1.7) for _ in vs]
        try:
            i = vs.index(v); h = 1e-5
            a = list(p); b = list(p); a[i] += h; b[i] -= h
            num = (f(*a) - f(*b)) / (2 * h); ex = g(*p)
            if isinstance(num, complex) or isinstance(ex, complex): continue
            tot += 1
            if abs(num - ex) <= 1e-5 * (1 + abs(ex)): ok += 1
        except Exception:
            continue
    return "passed" if tot >= 3 and ok == tot else ("not_possible" if tot < 3 else "failed")


def _ver(estados):
    if "failed" in estados: return "failed"
    return "passed" if estados and all(e == "passed" for e in estados) else "not_possible"


def _res(exacto, latex, pasos, ver, metodo, aprox=None, data=None):
    return {"status": "success_exact", "exact_result": exacto, "approximate_result": aprox, "latex": {"result": latex}, "method": metodo,
            "verification": {"status": ver, "method": "diferencias finitas centradas (independiente)" if "finitas" in metodo or True else ""},
            "steps": pasos, "data": data or {}}


def run(p):
    op = p.get("op")
    vs = list(p.get("variables") or ["x", "y", "z"])
    if op == "gradiente":
        f = p["f"]; pasos = [{"text": "Gradiente: vector de derivadas parciales", "latex": r"\nabla f = \left(" + ",".join(r"\frac{\partial f}{\partial %s}" % v for v in vs) + r"\right)"}]
        ds = []; ver = []
        for v in vs:
            d = derivar(f, v); ds.append(d); ver.append(_chk_deriv(f, v, d, vs))
            pasos.append({"text": f"∂f/∂{v}", "latex": r"\frac{\partial f}{\partial %s} = %s" % (v, d.to_str(True))})
        if "failed" in ver: raise VerificationFailed("La verificación de las derivadas falló", {})
        return _res("(" + ", ".join(d.to_str() for d in ds) + ")", r"\nabla f = \left(" + ",".join(d.to_str(True) for d in ds) + r"\right)", pasos, _ver(ver), "gradiente")
    if op == "laplaciano":
        f = p["f"]; pasos = []; tot = None; ver = []
        for v in vs:
            d1 = derivar(f, v); d2 = d1.deriv(v)
            ver.append(_chk_deriv(d1.to_str(), v, d2, vs)); ver.append(_chk_deriv(f, v, d1, vs))
            pasos.append({"text": f"∂²f/∂{v}²", "latex": r"\frac{\partial^2 f}{\partial %s^2} = %s" % (v, d2.to_str(True))})
            tot = d2 if tot is None else tot + d2
        pasos.append({"text": "Laplaciano = suma de las segundas derivadas parciales", "latex": r"\nabla^2 f = %s" % tot.to_str(True)})
        return _res(tot.to_str(), tot.to_str(True), pasos, _ver(ver), "laplaciano")
    comps = list(p.get("campo") or [])
    if op == "divergencia":
        if len(comps) != len(vs): raise InvalidRequest("El campo debe tener tantas componentes como variables")
        pasos = [{"text": "Divergencia: suma de ∂Fᵢ/∂xᵢ", "latex": r"\nabla\cdot F = " + "+".join(r"\frac{\partial F_%d}{\partial %s}" % (i + 1, v) for i, v in enumerate(vs))}]
        tot = None; ver = []
        for c, v in zip(comps, vs):
            d = derivar(c, v); ver.append(_chk_deriv(c, v, d, vs))
            pasos.append({"text": f"∂/∂{v} de ({c})", "latex": r"= %s" % d.to_str(True)})
            tot = d if tot is None else tot + d
        pasos.append({"text": "Suma", "latex": r"\nabla\cdot F = %s" % tot.to_str(True)})
        return _res(tot.to_str(), tot.to_str(True), pasos, _ver(ver), "divergencia")
    if op == "rotacional":
        ver = []
        def d(c, v): r = derivar(c, v); ver.append(_chk_deriv(c, v, r, vs)); return r
        if len(comps) == 3:
            P, Q, R = comps
            i = d(R, "y") - d(Q, "z"); j = d(P, "z") - d(R, "x"); k = d(Q, "x") - d(P, "y")
            pasos = [{"text": "Rotacional (determinante simbólico)", "latex": r"\nabla\times F = \left(\partial_y R-\partial_z Q,\ \partial_z P-\partial_x R,\ \partial_x Q-\partial_y P\right)"},
                     {"text": "Componentes", "latex": r"\left(%s,\ %s,\ %s\right)" % (i.to_str(True), j.to_str(True), k.to_str(True))}]
            ex = "(" + ", ".join(e.to_str() for e in (i, j, k)) + ")"
            cero = all(e.is_zero() for e in (i, j, k))
            if cero: pasos.append({"text": "El rotacional es el vector nulo: el campo es irrotacional (conservativo en un dominio simplemente conexo)"})
            return _res(ex, r"\left(%s,%s,%s\right)" % (i.to_str(True), j.to_str(True), k.to_str(True)), pasos, _ver(ver), "rotacional", data={"irrotacional": cero})
        if len(comps) == 2:
            P, Q = comps
            r = d(Q, "x") - d(P, "y")
            pasos = [{"text": "Rotacional escalar en el plano: ∂Q/∂x − ∂P/∂y", "latex": r"\partial_x Q-\partial_y P = %s" % r.to_str(True)}]
            return _res(r.to_str(), r.to_str(True), pasos, _ver(ver), "rotacional", data={"irrotacional": r.is_zero()})
        raise InvalidRequest("El campo debe tener 2 o 3 componentes")
    if op == "conservativo":
        return _conservativo(comps, vs)
    if op == "linea":
        return _linea(p, comps)
    raise InvalidRequest("op vectorial no reconocida")


def _conservativo(comps, vs):
    n = len(comps); vs = vs[:n]
    ver = []
    pasos = [{"text": "Un campo F es conservativo (en un dominio simplemente conexo) si ∂Fᵢ/∂xⱼ = ∂Fⱼ/∂xᵢ para todo par (i, j)"}]
    ok = True
    for i in range(n):
        for j in range(i + 1, n):
            a = derivar(comps[i], vs[j]); b = derivar(comps[j], vs[i])
            ver += [_chk_deriv(comps[i], vs[j], a, vs), _chk_deriv(comps[j], vs[i], b, vs)]
            igual = (a - b).is_zero()
            pasos.append({"text": f"∂F{i+1}/∂{vs[j]} = {a.to_str()}  y  ∂F{j+1}/∂{vs[i]} = {b.to_str()}", "latex": None})
            ok = ok and igual
    if not ok:
        return {"status": "success_exact", "exact_result": "El campo NO es conservativo (no existe función potencial)", "approximate_result": None,
                "method": "criterio_de_derivadas_cruzadas", "verification": {"status": _ver(ver), "method": "diferencias finitas centradas (independiente)"},
                "steps": pasos, "data": {"conservativo": False}}
    # función potencial: φ = ∫F1 dx + g(y,z) …
    pot = integra.integrate(_E(comps[0]), vs[0])
    pasos.append({"text": f"Función potencial: se integra F1 respecto de {vs[0]}", "latex": r"\varphi = %s + g" % pot.to_str(True)})
    for k in range(1, n):
        resto = _E(comps[k]) - pot.deriv(vs[k])
        if resto.is_zero(): continue
        extra = integra.integrate(resto, vs[k])
        pot = pot + extra
        pasos.append({"text": f"Se completa con lo que falta de F{k+1} (derivando φ respecto de {vs[k]} y comparando)", "latex": r"\varphi = %s" % pot.to_str(True)})
    # comprobación: ∇φ = F
    for c, v in zip(comps, vs):
        if not (pot.deriv(v) - _E(c)).is_zero(): raise VerificationFailed("El potencial hallado no reproduce el campo", {})
    pasos.append({"text": "Comprobación exacta: ∇φ = F en cada componente"})
    return {"status": "success_exact", "exact_result": f"φ = {pot.to_str()} + C", "approximate_result": None, "latex": {"result": r"\varphi = %s + C" % pot.to_str(True)},
            "method": "funcion_potencial", "verification": {"status": "passed", "method": "∇φ − F = 0 (comprobación exacta)"}, "steps": pasos, "data": {"conservativo": True, "potencial": pot.to_str()}}


def _sust(expr_txt, mapa):
    a = _A(expr_txt)
    for v, rep in mapa.items(): a = ast_subs(a, v, _A(rep))
    return a


def _linea(p, comps):
    """∫_C F·dr  (o  ∫_C f ds si p['escalar'])  con la curva paramétrica p['curva'] = {x:…, y:…, [z:…], t:[a,b]}"""
    cv = p["curva"]; vs = ["x", "y", "z"][:len(comps)] if comps else ["x", "y", "z"]
    t0, t1 = str(cv["t"][0]), str(cv["t"][1])
    coords = {v: cv[v] for v in vs if v in cv}
    ds = {v: _E(coords[v]).deriv("t") for v in coords}
    pasos = [{"text": "Parametrización de la curva C: " + ", ".join(f"{v}(t) = {coords[v]}" for v in coords) + f",  t de {t0} a {t1}", "latex": None},
             {"text": "Derivadas de la parametrización", "latex": ",\\ ".join("%s'(t) = %s" % (v, ds[v].to_str(True)) for v in ds)}]
    if p.get("escalar"):
        f = p["f"]
        rad = "+".join(f"({ds[v].to_str()})^2" for v in coords)
        integrando = f"({_sust_str(f, coords)})*sqrt({rad})"
        etiqueta = "Integral de línea escalar ∫ f ds = ∫ f(r(t))·|r'(t)| dt"
    else:
        terminos = [f"({_sust_str(c, coords)})*({ds[v].to_str()})" for c, v in zip(comps, vs)]
        integrando = "+".join(terminos)
        etiqueta = "Trabajo/circulación ∫ F·dr = ∫ F(r(t))·r'(t) dt"
    pasos.append({"text": etiqueta, "latex": None})
    fe = _E(integrando)
    niv = [{"var": "t", "lo": _E(t0), "hi": _E(t1)}]
    r = integrar(fe, niv, nombre="W")
    pasos.extend(r["pasos"])
    if r["verificacion"] == "failed": raise VerificationFailed("La verificación por cuadratura de la integral de línea falló", {})
    ex = r["exacto"]; aprox = r["aprox"]
    extra_ver = None
    gr = p.get("green")
    if gr and ex is not None and not p.get("escalar"):
        v2 = _green(comps, gr)
        if v2 is not None:
            pasos.append({"text": f"Contraste por el teorema de Green: ∬ (∂Q/∂x − ∂P/∂y) dA = {_fmt_num(v2)}", "latex": None})
            if abs(v2 - aprox) > 1e-6 * (1 + abs(aprox)):
                raise VerificationFailed("El teorema de Green no coincide con la integral de línea", {"linea": aprox, "green": v2})
            extra_ver = "teorema de Green"
    out = {"status": "success_exact" if ex is not None else "success_approximate", "exact_result": ex.to_str() if ex is not None else None,
           "approximate_result": _fmt_num(aprox), "method": "integral_de_linea",
           "verification": {"status": r["verificacion"], "method": "cuadratura numérica independiente" + (" + " + extra_ver if extra_ver else "")},
           "steps": pasos, "data": {}}
    if ex is not None: out["latex"] = {"result": ex.to_str(True)}
    return out


def _sust_str(f, coords):
    return ast_str(_sust(f, coords))


def _green(comps, gr):
    """∬_D (Q_x − P_y) dA para un disco de centro (cx,cy) y radio R con orientación gr['signo']; devuelve el valor numérico"""
    P, Q = comps[0], comps[1]
    cx, cy, R, signo = gr["cx"], gr["cy"], gr["R"], gr["signo"]
    h = (_E(Q).deriv("x") - _E(P).deriv("y")).to_str()
    f = _sust(h, {"x": f"({cx})+r*cos(theta)", "y": f"({cy})+r*sin(theta)"})
    fe = from_ast(("bin", "*", f, _A("r")))
    niv = [{"var": "r", "lo": _E("0"), "hi": _E(str(R))}, {"var": "theta", "lo": _E("0"), "hi": _E("2*pi")}]
    r = integrar(fe, niv, nombre="G")
    return signo * r["aprox"]
