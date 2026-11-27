"""Puerta de entrada de Matemática III: despacha por params.tipo y entrega resultados en el formato del contrato."""
import math
from fractions import Fraction as F
from ..errors import InvalidRequest, VerificationFailed, NotImplementedOperation, MathDomainError
from .cas3 import Expr, GP, NoSoportado, NoPrimitiva, from_ast
from . import aplicaciones as AP, coords as CO, cambio as CA, extremos as EX, lagrange as LG, parametros as PA
from .iterada import integrar, lat, lat_integral, _fmt_num
from ..parser import parse
from ..ast_tools import normalize

TIPOS = ("iterada", "region", "triple_region", "coordenadas", "jacobiano", "cambio_variables", "cambio_variables_3d",
         "extremos", "lagrange", "ajuste_lineal", "parametros_extremo", "parametros_condicion", "cambio_orden")


def _P(s): return from_ast(normalize(parse(s)))


def _req(p, k):
    if k not in p or p[k] in (None, "", []): raise InvalidRequest(f"Falta el dato «{k}» en params")
    return p[k]


def _niveles(lst):
    out = []
    for it in lst:
        if len(it) != 3: raise InvalidRequest("Cada nivel debe ser [variable, límite inferior, límite superior]")
        out.append({"var": str(it[0]), "lo": _P(str(it[1])), "hi": _P(str(it[2]))})
    return out


def _fin(res, metodo):
    """Convierte el resultado interno en respuesta del contrato"""
    ex = res.get("exacto")
    out = {"method": metodo}
    ver = res.get("verificacion", "not_possible")
    if ver == "failed":
        raise VerificationFailed("La verificación independiente falló: el resultado no se entrega como válido",
                                 {"unverified_result": str(ex) if ex is not None else res.get("aprox"), "method": "cuadratura_tanh_sinh"})
    out["verification"] = {"status": ver, "method": "cuadratura numérica independiente (tanh-sinh anidada)"}
    if ex is not None:
        out["status"] = "success_exact"; out["exact_result"] = ex.to_str() if isinstance(ex, Expr) else str(ex)
        out["approximate_result"] = _fmt_num(res["aprox"]) if res.get("aprox") is not None else None
        out["latex"] = {"result": ex.to_str(True) if isinstance(ex, Expr) else str(ex)}
    else:
        out["status"] = "success_approximate"; out["exact_result"] = None
        out["approximate_result"] = _fmt_num(res["aprox"])
        out["warnings"] = [res.get("metodo_aviso") or "Sin forma cerrada con las reglas del curso: valor numérico verificado"]
    if res.get("avisos"): out.setdefault("warnings", []).extend(res["avisos"])
    out["steps"] = res.get("pasos", [])
    out["data"] = {"planteamiento": res.get("planteamiento")}
    return out


def run(req, st):
    p = dict(req.get("params") or {})
    tipo = p.get("tipo")
    if tipo not in ("suma", "auto", "cambio_variables_masa", "politopo", "vectorial", "superficie") and tipo not in TIPOS: raise InvalidRequest("params.tipo debe ser uno de: " + ", ".join(TIPOS))
    try:
        return _run(tipo, p, req, st)
    except NoSoportado as e:
        raise NotImplementedOperation("No soportado por el motor de Matemática III: " + str(e))
    except (ZeroDivisionError, ValueError) as e:
        raise MathDomainError("Operación fuera de dominio: " + str(e))


def _suma(p, req, st):
    """Suma de varias integrales/piezas (p. ej. regiones que se parten en dos): cada parte es una solicitud calc3 completa"""
    partes = _req(p, "partes")
    if len(partes) < 2: raise InvalidRequest("Se necesitan al menos dos partes")
    total = None; aprox = 0.0; pasos = []; todas_ok = True
    for i, q in enumerate(partes, 1):
        q = dict(q)
        if q.get("tipo") in (None, "suma"): raise InvalidRequest("Cada parte debe tener un tipo de ejercicio (no «suma»)")
        r = _run(q["tipo"], q, req, st)
        ex = r.get("exact_result")
        if r.get("status") != "success_exact" or ex is None or "=" in str(ex):
            raise InvalidRequest(f"La parte {i} no da un único valor exacto; no se puede sumar")
        e = _P(str(ex)); total = e if total is None else total + e
        aprox += float(str(r["approximate_result"]).split()[0])
        todas_ok = todas_ok and r.get("verification", {}).get("status") == "passed"
        pasos.append({"text": f"Parte {i}: resultado {ex}"})
        pasos.extend(dict(x, text=f"[parte {i}] " + x["text"]) for x in r.get("steps", []))
    pasos.append({"text": "Resultado total = suma de las partes", "latex": total.to_str(True)})
    return {"status": "success_exact", "exact_result": total.to_str(), "approximate_result": _fmt_num(aprox), "method": "suma_de_integrales",
            "latex": {"result": total.to_str(True)},
            "verification": {"status": "passed" if todas_ok else "not_possible", "method": "cuadratura numérica independiente de cada parte"},
            "steps": pasos, "data": {"partes": len(partes)}}


def _politopo(p):
    """integrales / áreas / volúmenes / masas / centroides / inercias sobre una región lineal (politopo), exactos"""
    from . import politopo as PO
    vs = list(p.get("variables") or ["x", "y"])
    cons = PO.restricciones_desde_textos(_req(p, "restricciones"), vs)
    if cons is None: raise InvalidRequest("Las restricciones deben ser lineales")
    que = p.get("que", "integral"); orden = list(p.get("orden") or vs)
    delta = p.get("delta") or "1"
    def uno(f, nom):
        r = PO.integrar_politopo(cons, orden, f, nombre=nom)
        if r["verificacion"] == "failed": raise VerificationFailed("La verificación independiente falló", {"integral": nom})
        return r
    def ex(r): return r["exacto"]
    pasos = []
    def reg(r, rot):
        pasos.extend(dict(x, text=f"[{rot}] " + x["text"]) for x in r["pasos"])
    if que in ("masa", "centroide"):
        m = uno(f"({delta})", "m"); reg(m, "masa")
        ms = []
        for v in vs:
            r = uno(f"({delta})*({v})", "M_" + v); reg(r, f"momento respecto a {v}"); ms.append(r)
        cs = [(AP._cociente(r["exacto"], m["exacto"]), r["aprox"] / m["aprox"]) for r in ms]
        ver = "passed" if all(r["verificacion"] == "passed" for r in [m] + ms) else "not_possible"
        def s_(c, a): return c.to_str() if c is not None else _fmt_num(a)
        pasos.append({"text": "Coordenadas del centro de masa (momento / masa)", "latex": None})
        return {"status": "success_exact", "exact_result": f"m = {m['exacto'].to_str()}; centro de masa = (" + ", ".join(s_(c, a) for c, a in cs) + ")",
                "approximate_result": f"m ≈ {_fmt_num(m['aprox'])}; centro ≈ (" + ", ".join(_fmt_num(a) for _, a in cs) + ")",
                "method": "politopo_masa_y_centro", "verification": {"status": ver, "method": "cuadratura numérica independiente de cada pieza"},
                "steps": pasos, "data": {"m": m["aprox"], "centro": [a for _, a in cs], "piezas": m["piezas"]}}
    if que == "inercia":
        eje = p.get("eje") or ("z" if len(vs) == 2 else None)
        if eje is None: raise InvalidRequest("Indique el eje respecto al cual se calcula el momento de inercia")
        otros = [v for v in vs if v != eje] if eje in vs else vs
        r = uno(f"({delta})*(" + "+".join(f"{v}^2" for v in otros) + ")", "I_" + eje); reg(r, "inercia")
        f = None
    else:
        f = p.get("f") or "1"
        if que in ("area", "volumen"): f = "1"
        r = uno(f, "V" if f == "1" else "I"); reg(r, "integral")
    out = {"status": "success_exact", "exact_result": r["exacto"].to_str(), "approximate_result": _fmt_num(r["aprox"]),
           "latex": {"result": r["exacto"].to_str(True)}, "method": "politopo_integral_exacta",
           "verification": {"status": r["verificacion"], "method": "cuadratura numérica independiente de cada pieza"},
           "steps": pasos, "data": {"piezas": r["piezas"]}}
    return out


def _run(tipo, p, req, st):
    if tipo == "politopo":
        return _politopo(p)
    if tipo == "vectorial":
        from . import vectorial
        return vectorial.run(p)
    if tipo == "auto":
        from . import enunciado
        return enunciado.resolver(_req(p, "texto"), req, st)
    if tipo == "suma":
        return _suma(p, req, st)
    if tipo == "iterada":
        f = _P(_req(p, "f")); niv = _niveles(_req(p, "niveles"))
        return _fin(integrar(f, niv, nombre="I"), "integral_iterada_exacta")
    if tipo == "region":
        curvas = _req(p, "curvas"); orden = p.get("orden", "dydx"); pt = _punto(p)
        que = p.get("que", "area")
        if orden not in ("dydx", "dxdy"): raise InvalidRequest("orden debe ser dydx o dxdy")
        if que == "area": r = AP.area(curvas, orden, punto=pt); return _fin(r, "area_por_integral_doble")
        if que == "volumen": r = AP.volumen(_req(p, "z"), curvas, orden, punto=pt); return _fin(r, "volumen_por_integral_doble")
        if que == "integral": r = AP.integral_region(_P(_req(p, "f")), curvas, orden, nombre="I", punto=pt); return _fin(r, "integral_doble")
        if que == "masa":
            r = AP.masa_centroide(_req(p, "delta"), curvas, orden, punto=pt)
            return _fin_masa(r)
        raise InvalidRequest("params.que debe ser area, volumen, integral o masa")
    if tipo == "cambio_orden":
        curvas = _req(p, "curvas"); f = _P(p.get("f", "1")); pt = _punto(p)
        a = AP.integral_region(f, curvas, "dydx", nombre="I", punto=pt)
        b = AP.integral_region(f, curvas, "dxdy", nombre="I", punto=pt)
        base, otro, nb = (a, b, "dy dx") if a["exacto"] is not None or b["exacto"] is None else (b, a, "dx dy")
        out = _fin(base, "cambio_de_orden")
        coinciden = abs(a["aprox"] - b["aprox"]) < 1e-8 * (1 + abs(a["aprox"]))
        if not coinciden:
            raise VerificationFailed("Los dos órdenes de integración no coinciden", {"dydx": a["aprox"], "dxdy": b["aprox"]})
        out["data"] = {"dydx": a["planteamiento"], "dxdy": b["planteamiento"], "coinciden": coinciden,
                       "orden_con_primitiva": nb if base["exacto"] is not None else None}
        nota = []
        if otro["exacto"] is None and base["exacto"] is not None:
            nota.append({"text": "En el orden " + ("dx dy" if nb == "dy dx" else "dy dx") + " no hay primitiva elemental en algún paso; por eso se resuelve en el orden " + nb, "latex": None})
        out["steps"] = ([{"text": "Orden dy dx", "latex": a["planteamiento"]}, {"text": "Orden dx dy", "latex": b["planteamiento"]}] + nota + base["pasos"])
        return out
    if tipo == "triple_region" and p.get("que", "integral") in ("masa3d", "inercia"):
        run1 = lambda f, nom: AP.triple_sobre_region(f, _req(p, "z_inf"), _req(p, "z_sup"), p.get("curvas", []), p.get("orden", "dydx"),
                                                      punto=_punto(p), nombre=nom, proyeccion_auto=p.get("proyeccion_auto", True))
        return _solido(run1, p)
    if tipo == "triple_region":
        r = AP.triple_sobre_region(p.get("f", "1"), _req(p, "z_inf"), _req(p, "z_sup"), p.get("curvas", []), p.get("orden", "dydx"),
                                   punto=_punto(p), nombre="V" if p.get("f", "1") == "1" else "I", proyeccion_auto=p.get("proyeccion_auto", True))
        return _fin(r, "integral_triple_entre_superficies")
    if tipo == "coordenadas":
        sis = _req(p, "sistema")
        if sis not in CO.SIS: raise InvalidRequest("sistema: polares, cilindricas o esfericas")
        niv = [(str(a), str(b), str(c)) for a, b, c in _req(p, "niveles")]
        if p.get("que") == "masa2d":
            return _masa2d(lambda f, nom: CO.integral(f, sis, niv, nombre=nom), p)
        if p.get("que", "integral") in ("masa3d", "inercia"):
            return _solido(lambda f, nom: CO.integral(f, sis, niv, nombre=nom), p)
        return _fin(CO.integral(p.get("f", "1"), sis, niv), "coordenadas_" + sis)
    if tipo == "jacobiano":
        old = list(_req(p, "viejas")); new = list(_req(p, "nuevas"))
        r = CA.jacobiano(old, new, _req(p, "mapa"), p.get("modo", "directo"))
        J = r["J"]
        return {"status": "success_exact", "exact_result": J.to_str(), "approximate_result": None, "method": "jacobiano_simbolico",
                "verification": {"status": "not_performed", "method": None}, "steps": r["pasos"], "data": {"J": J.to_str(), "latex": J.to_str(True)}}
    if tipo == "cambio_variables_masa":
        d = _req(p, "delta")
        def uno(f):
            return CA.cambio_variables_doble(f, _req(p, "curvas"), list(_req(p, "nuevas")), _req(p, "mapa"), p.get("modo", "inverso"),
                                             p.get("orden", "dydx"), punto=_punto(p))
        m, My, Mx = uno(f"({d})"), uno(f"({d})*x"), uno(f"({d})*y")
        for k in (m, My, Mx):
            if k.get("verificacion") == "failed": raise VerificationFailed("La verificación independiente falló", {})
        xb = AP._cociente(My["exacto"], m["exacto"]) if m["exacto"] is not None and My["exacto"] is not None else None
        yb = AP._cociente(Mx["exacto"], m["exacto"]) if m["exacto"] is not None and Mx["exacto"] is not None else None
        r = {"m": m, "My": My, "Mx": Mx, "xbar": xb, "ybar": yb, "xbar_aprox": My["aprox"] / m["aprox"], "ybar_aprox": Mx["aprox"] / m["aprox"]}
        return _fin_masa(r)
    if tipo == "cambio_variables":
        r = CA.cambio_variables_doble(_req(p, "f"), _req(p, "curvas"), list(_req(p, "nuevas")), _req(p, "mapa"), p.get("modo", "inverso"),
                                      p.get("orden", "dydx"), punto=_punto(p))
        out = _fin(r, "cambio_de_variables")
        out["data"]["jacobiano"] = r["jacobiano"].to_str()
        return out
    if tipo == "cambio_variables_3d":
        r = CA.cambio_variables_caja(_req(p, "f"), list(_req(p, "viejas")), list(_req(p, "nuevas")), _req(p, "mapa"), p.get("modo", "inverso"), _niveles(_req(p, "niveles")))
        out = _fin(r, "cambio_de_variables_3d"); out["data"]["jacobiano"] = r["jacobiano"].to_str(); return out
    if tipo == "extremos":
        r = EX.extremos_locales(_req(p, "f"), list(_req(p, "variables")))
        return _fin_puntos(r, "extremos_locales_hessiana")
    if tipo == "lagrange":
        r = LG.lagrange(_req(p, "f"), list(_req(p, "restricciones")), list(_req(p, "variables")), positivo=bool(p.get("positivo")))
        return _fin_puntos(r, "multiplicadores_de_lagrange")
    if tipo == "ajuste_lineal":
        pts = [(F(str(a)), F(str(b))) for a, b in _req(p, "puntos")]
        r = PA.ajuste_lineal(pts)
        if r["verificacion"] != "passed": raise VerificationFailed("La verificación de las ecuaciones normales falló", {})
        m, b = r["m"], r["b"]
        return {"status": "success_exact", "exact_result": f"y = {m}*x + ({b})", "approximate_result": f"y = {float(m):.10g} x + {float(b):.10g}",
                "method": "minimos_cuadrados", "verification": {"status": "passed", "method": "gradiente nulo y Hessiana definida positiva (exacto)"},
                "steps": r["pasos"], "data": {"m": str(m), "b": str(b)}}
    if tipo == "parametros_extremo":
        r = PA.extremo_con_parametros(_req(p, "f"), list(_req(p, "variables")), [F(str(c)) for c in _req(p, "punto")], list(_req(p, "parametros")), p.get("valor"))
        txt = ", ".join(f"{k} = {v}" for k, v in r["params"].items())
        return {"status": "success_exact", "exact_result": txt, "approximate_result": None, "method": "condiciones_de_extremo_con_parametros",
                "verification": {"status": "passed", "method": "clasificación por Hessiana con los parámetros hallados"}, "steps": r["pasos"], "data": {"clase": r["clase"]}}
    if tipo == "parametros_condicion":
        r = PA.condicion_parametro(_req(p, "f"), list(_req(p, "variables")), [F(str(c)) for c in _req(p, "punto")], _req(p, "parametro"), p.get("extremo", "minimo"))
        return {"status": "success_exact", "exact_result": r["condicion"], "approximate_result": None, "method": "sylvester_con_parametro",
                "verification": {"status": "not_performed", "method": None}, "steps": r["pasos"], "data": {}}
    raise InvalidRequest("tipo no implementado")


def _punto(p):
    pt = p.get("punto")
    if pt is None: return None
    return (float(F(str(pt[0]))), float(F(str(pt[1]))))


def _fin_masa(r):
    m, My, Mx = r["m"], r["My"], r["Mx"]
    for k in (m, My, Mx):
        if k.get("verificacion") == "failed":
            raise VerificationFailed("La verificación independiente falló", {})
    xb, yb = r["xbar"], r["ybar"]
    def s(e, a): return e.to_str() if e is not None else _fmt_num(a)
    pasos = []
    pasos += [dict(x, text="[masa] " + x["text"]) for x in m["pasos"]]
    pasos += [dict(x, text="[M_y = ∬ x·δ dA] " + x["text"]) for x in My["pasos"]]
    pasos += [dict(x, text="[M_x = ∬ y·δ dA] " + x["text"]) for x in Mx["pasos"]]
    pasos.append({"text": "Centro de masa", "latex": r"\bar{x} = \frac{M_y}{m} = %s \approx %s,\qquad \bar{y} = \frac{M_x}{m} = %s \approx %s" % (
        (xb.to_str(True) if xb is not None else _fmt_num(r["xbar_aprox"])), _fmt_num(r["xbar_aprox"]),
        (yb.to_str(True) if yb is not None else _fmt_num(r["ybar_aprox"])), _fmt_num(r["ybar_aprox"]))})
    exact = m["exacto"] is not None
    ver = "passed" if all(k.get("verificacion") == "passed" for k in (m, My, Mx)) else "not_possible"
    out = {"status": "success_exact" if exact else "success_approximate",
           "exact_result": f"m = {s(m['exacto'], m['aprox'])}; centro de masa = ({s(xb, r['xbar_aprox'])}, {s(yb, r['ybar_aprox'])})",
           "approximate_result": f"m ≈ {_fmt_num(m['aprox'])}; (x̄, ȳ) ≈ ({_fmt_num(r['xbar_aprox'])}, {_fmt_num(r['ybar_aprox'])})",
           "method": "masa_y_centro_de_masa", "verification": {"status": ver, "method": "cuadratura numérica independiente (tanh-sinh anidada)"},
           "steps": pasos, "data": {"m": m["aprox"], "My": My["aprox"], "Mx": Mx["aprox"], "xbar": r["xbar_aprox"], "ybar": r["ybar_aprox"]}}
    return out


def _masa2d(run1, p):
    d = p.get("delta", "1")
    m, My, Mx = run1(f"({d})", "m"), run1(f"({d})*(x)", "M_y"), run1(f"({d})*(y)", "M_x")
    xb = AP._cociente(My["exacto"], m["exacto"]) if m["exacto"] is not None and My["exacto"] is not None else None
    yb = AP._cociente(Mx["exacto"], m["exacto"]) if m["exacto"] is not None and Mx["exacto"] is not None else None
    return _fin_masa({"m": m, "My": My, "Mx": Mx, "xbar": xb, "ybar": yb, "xbar_aprox": My["aprox"] / m["aprox"], "ybar_aprox": Mx["aprox"] / m["aprox"]})


def _solido(run1, p):
    """masa y centro de masa de un sólido, o momento de inercia respecto de un eje coordenado"""
    delta = p.get("delta", "1")
    pasos = []; res = {}
    def uno(nom, f):
        r = run1(f, nom)
        if r.get("verificacion") == "failed": raise VerificationFailed("La verificación independiente falló", {"integral": nom})
        res[nom] = r
        pasos.extend(dict(x, text=f"[{nom}] " + x["text"]) for x in r["pasos"])
        return r
    if p.get("que") == "inercia":
        eje = p.get("eje", "z")
        suma = {"x": "y^2+z^2", "y": "x^2+z^2", "z": "x^2+y^2"}.get(eje)
        if suma is None: raise InvalidRequest("eje debe ser x, y o z")
        r = uno("I_" + eje, f"({delta})*({suma})")
        out = _fin(r, "momento_de_inercia"); out["steps"] = pasos; return out
    m = uno("m", f"({delta})")
    Mx = uno("M_yz", f"({delta})*(x)"); My = uno("M_xz", f"({delta})*(y)"); Mz = uno("M_xy", f"({delta})*(z)")
    cs = []
    for M in (Mx, My, Mz):
        c = AP._cociente(M["exacto"], m["exacto"]) if (m["exacto"] is not None and M["exacto"] is not None) else None
        cs.append((c, M["aprox"] / m["aprox"]))
    exact = m["exacto"] is not None
    def s_(c, a): return c.to_str() if c is not None else _fmt_num(a)
    pasos.append({"text": "Centro de masa", "latex": r"\bar{x}=\frac{M_{yz}}{m} = %s,\quad \bar{y} = \frac{M_{xz}}{m} = %s,\quad \bar{z} = \frac{M_{xy}}{m} = %s" % tuple(
        (c.to_str(True) if c is not None else _fmt_num(a)) for c, a in cs)})
    ver = "passed" if all(r.get("verificacion") == "passed" for r in res.values()) else "not_possible"
    return {"status": "success_exact" if exact else "success_approximate",
            "exact_result": f"m = {s_(m['exacto'], m['aprox'])}; centro de masa = (" + ", ".join(s_(c, a) for c, a in cs) + ")",
            "approximate_result": f"m ≈ {_fmt_num(m['aprox'])}; centro ≈ (" + ", ".join(_fmt_num(a) for _, a in cs) + ")",
            "method": "masa_y_centro_de_masa_3d", "verification": {"status": ver, "method": "cuadratura numérica independiente (tanh-sinh anidada)"},
            "steps": pasos, "data": {"m": m["aprox"], "centro": [a for _, a in cs]}}


def _fin_puntos(r, metodo):
    pts = r["puntos"]
    def coord(c): return EX._fmt_coord(c)
    lineas = []
    for k, pt in enumerate(pts):
        fv = pt["f"]
        fs = fv.to_str() if isinstance(fv, Expr) else _fmt_num(fv)
        lineas.append(f"P{k + 1}(" + ", ".join(coord(c) for c in pt["punto"]) + f"), f = {fs}: " + pt.get("clase", ""))
    data = {"puntos": [{"coordenadas": [coord(c) for c in pt["punto"]], "valor": (pt["f"].to_str() if isinstance(pt["f"], Expr) else _fmt_num(pt["f"])),
                        "valor_aprox": pt["fnum"] if "fnum" in pt else None, "clase": pt.get("clase"),
                        "multiplicadores": [coord(c) for c in pt.get("lam", [])], "verificacion": pt.get("verif")} for pt in pts]}
    out = {"status": "success_exact" if pts else "no_solution", "exact_result": "\n".join(lineas) if lineas else "No se encontraron puntos críticos reales",
           "approximate_result": None, "method": metodo,
           "verification": {"status": "passed" if pts and all(pt.get("verif") in ("exacta", "numerica") for pt in pts) else "not_possible",
                            "method": "sustitución exacta en el sistema de ecuaciones (o numérica donde hay radicales distintos)"},
           "steps": r["pasos"], "data": data,
           "warnings": ["Los puntos críticos se buscan con un barrido de puntos de partida (Newton); en sistemas con muchas soluciones puede faltar alguna. Cada punto listado se comprueba."]}
    return out
