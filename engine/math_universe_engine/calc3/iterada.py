"""Integrales iteradas con procedimiento paso a paso (formato de clase) y verificación por cuadratura."""
import math
from fractions import Fraction as F
from .cas3 import GP, Expr, NoPrimitiva, NoSoportado
from . import integra
from .numerico import integral as quad


def lat(e, latex=True):
    return e.to_str(latex) if isinstance(e, Expr) else Expr.of(e).to_str(latex)


def lat_integral(niveles, cuerpo, latex=True):
    """niveles: de la más interna a la más externa (dicts var/lo/hi). Devuelve  ∫_a^b … ∫_c^d cuerpo dv1 … dvn"""
    ext = "".join((r"\int_{%s}^{%s}" % (lat(n["lo"]), lat(n["hi"]))) for n in reversed(niveles))
    difs = "".join(r"\,d%s" % n["var"] for n in niveles)
    return f"{ext} {cuerpo}{difs}"


def _fmt_num(x):
    if abs(x) >= 1e5 or (x != 0 and abs(x) < 1e-4): return f"{x:.10e}"
    return f"{x:.10g}"


def evaluar_exacto(e):
    try: return e.eval({})
    except Exception: return None


def valor_en(Fv, v, b, notas=None):
    """Fv evaluada en v=b; si b=0 y hay ln(v)/potencias que tienden a 0 (integral impropia) se usa el límite."""
    try:
        return Fv.subs(v, b)
    except NoSoportado:
        if not (b.is_gp() and b.gp().is_zero()): raise
    from .cas3 import _gk
    out = Expr()
    for (e, a), c in Fv.t.items():
        depa = [(k, ak, n) for k, ak, n in a if _gk(ak).has(v)]
        if not c.has(v) and not depa and not (e and _gk(e).has(v)):
            out = out + Expr({(e, a): c}); continue
        if e and _gk(e).has(v): raise NoSoportado("límite en 0 con exponencial")
        if all(k == "ln" and _gk(ak) == GP.var(v) for k, ak, n in depa) and all(ex > 0 for ex in c.coef_in(v)):
            continue                       # v^a·ln^k(v) → 0 cuando v → 0⁺ (a > 0)
        raise NoSoportado("límite en 0 no reconocido")
    if notas is not None: notas.append("Límite en 0 por la derecha (integral impropia convergente): x^a·ln^k(x) → 0 si a > 0")
    return out


def integrar(f, niveles, f_num=None, nombre="I", detalle=True):
    """f: Expr. niveles: lista [{var, lo: Expr, hi: Expr}] de la más interna a la más externa.
    Devuelve dict(exacto: Expr|None, aprox: float, pasos, verificacion, metodo)."""
    pasos = []
    pasos.append({"text": "Planteamiento", "latex": f"{nombre} = " + lat_integral(niveles, lat(f))})
    cur = f; fallo = None; notas = []
    n = len(niveles)
    for i, lv in enumerate(niveles):
        v, lo, hi = lv["var"], lv["lo"], lv["hi"]
        resto = [niveles[j]["var"] for j in range(i + 1, n)]
        nom = ("Integral interna" if i == 0 else ("Integral externa" if i == n - 1 else f"Integral intermedia"))
        const_txt = (f"; {', '.join(resto)} se tratan como constantes" if (resto and i < n - 1) else "")
        if i == n - 1 and n > 1: const_txt = ""
        if i == 0 and n > 1: const_txt = f" (respecto a {v}{const_txt.replace(';', ', ') if const_txt else ''})"
        else: const_txt = f" (respecto a {v})"
        try:
            Fv = integra.integrate(cur, v)
        except (NoPrimitiva, NoSoportado) as e:
            fallo = (i, str(e)); break
        try:
            up, dn = valor_en(Fv, v, hi, notas), valor_en(Fv, v, lo, notas)
        except NoSoportado as e:
            fallo = (i, str(e)); break
        val = up - dn
        pasos.append({"text": nom + const_txt + ": se busca la primitiva y se evalúa en los límites",
                      "latex": r"\int_{%s}^{%s} %s\,d%s = \left[%s\right]_{%s}^{%s}" % (lat(lo), lat(hi), lat(cur), v, lat(Fv), lat(lo), lat(hi))})
        if not (lo.is_gp() and lo.gp().is_zero() or True):
            pass
        pasos.append({"text": "Se sustituyen los límites y se simplifica", "latex": r"= %s" % lat(val)})
        cur = val
    metodo = "integracion_iterada_exacta"
    exacto = None if fallo else cur
    # --- verificación independiente: cuadratura tanh-sinh anidada
    nombres = [lv["var"] for lv in reversed(niveles)]          # más externa primero
    if f_num is None:
        f_num = lambda *a, fe=f, nm=nombres: fe.eval(dict(zip(nm, a)))
    def mk(e, outer):
        return (lambda *a, e=e: e.eval(dict(zip(outer, a)))) if isinstance(e, Expr) else e
    bounds = []
    for i, lv in enumerate(niveles):
        outer = nombres[:len(nombres) - 1 - i]
        lo, hi = lv["lo"], lv["hi"]
        def mkb(e, outer=outer):
            if e.is_gp() and e.gp().is_const(): c = e.gp().eval({}); return c
            return (lambda *a, e=e, outer=outer: e.eval(dict(zip(outer, a))))
        bounds.append((mkb(lo), mkb(hi)))
    cuad, err = quad(f_num, bounds)
    for nt in dict.fromkeys(notas): pasos.insert(len(pasos) - (1 if exacto is not None else 0), {"text": nt, "latex": None})
    res = {"pasos": pasos, "cuadratura": cuad, "err_cuadratura": err}
    if exacto is not None:
        ap = evaluar_exacto(exacto)
        res["exacto"] = exacto; res["aprox"] = ap
        ok = ap is not None and abs(ap - cuad) <= 1e-7 * (1 + abs(ap)) + 10 * err
        res["verificacion"] = "passed" if ok else "failed"
        pasos.append({"text": "Resultado", "latex": f"{nombre} = {lat(exacto)} \\approx {_fmt_num(ap)}" if ap is not None else f"{nombre} = {lat(exacto)}"})
    else:
        res["exacto"] = None; res["aprox"] = cuad
        res["verificacion"] = "passed" if err < 1e-7 * (1 + abs(cuad)) else "not_possible"
        res["metodo_aviso"] = f"No se obtuvo primitiva elemental en el nivel {fallo[0] + 1} ({fallo[1]}); valor por cuadratura numérica verificada"
        res["fallo"] = fallo
        pasos.append({"text": "No hay primitiva elemental con las reglas del curso en este paso: el valor se obtiene por cuadratura numérica",
                      "latex": f"{nombre} \\approx {_fmt_num(cuad)}"})
        metodo = "cuadratura_numerica_tanh_sinh"
    res["metodo"] = metodo
    return res
