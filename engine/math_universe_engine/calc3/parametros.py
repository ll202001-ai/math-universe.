"""Problemas con parámetros (hoja 15, nº 13 y 14) y ajuste de mínimos cuadrados (hoja 16, nº 3)."""
import math
from fractions import Fraction as F
from . import extremos as X
from .cas3 import GP, Expr, from_ast, NoSoportado
from .iterada import lat
from ..ast_tools import subs as ast_subs, num as ast_num


def ajuste_lineal(puntos):
    """y = m x + b por mínimos cuadrados, exacto (Fraction). puntos: [(x, y)]"""
    P = [(F(a), F(b)) for a, b in puntos]; n = len(P)
    Sx = sum(a for a, _ in P); Sy = sum(b for _, b in P); Sxy = sum(a * b for a, b in P); Sxx = sum(a * a for a, _ in P)
    den = n * Sxx - Sx ** 2
    if den == 0: raise NoSoportado("todos los x son iguales: no hay recta de regresión")
    m = (n * Sxy - Sx * Sy) / den; b = (Sy - m * Sx) / n
    def fs(v): return str(v) if v.denominator == 1 else (r"\frac{%d}{%d}" % (v.numerator, v.denominator) if v > 0 else r"-\frac{%d}{%d}" % (-v.numerator, v.denominator))
    sq = " + ".join("(%s - (b + %s m))^2" % (fs(y), fs(x)) for x, y in P)
    pasos = [
        {"text": "Se minimiza la suma de los cuadrados de las diferencias verticales", "latex": r"f(b,m) = \sum (y_i - (b + m x_i))^2 = " + sq},
        {"text": "Condición de mínimo: ∂f/∂b = 0 y ∂f/∂m = 0  →  ecuaciones normales",
         "latex": r"\begin{cases} n\,b + m\sum x_i = \sum y_i \\ b\sum x_i + m\sum x_i^2 = \sum x_i y_i \end{cases}"},
        {"text": "Sumas necesarias", "latex": r"n = %d,\; \sum x = %s,\; \sum y = %s,\; \sum xy = %s,\; \sum x^2 = %s" % (n, fs(Sx), fs(Sy), fs(Sxy), fs(Sxx))},
        {"text": "Sistema con los valores", "latex": r"\begin{cases} %d\,b + %s\,m = %s \\ %s\,b + %s\,m = %s \end{cases}" % (n, fs(Sx), fs(Sy), fs(Sx), fs(Sxx), fs(Sxy))},
        {"text": "Solución (regla de Cramer)", "latex": r"m = \frac{n\sum xy - \sum x\sum y}{n\sum x^2 - (\sum x)^2} = %s,\qquad b = \frac{\sum y - m\sum x}{n} = %s" % (fs(m), fs(b))},
        {"text": "Recta de mínimos cuadrados", "latex": r"y = %s\,x %s %s" % (fs(m), "+" if b >= 0 else "-", fs(abs(b)))},
    ]
    # verificación independiente: el gradiente de f en (b,m) es cero y la Hessiana es definida positiva
    gb = sum(2 * (b + m * x - y) for x, y in P); gm = sum(2 * (b + m * x - y) * x for x, y in P)
    ok = gb == 0 and gm == 0 and (2 * n) > 0 and (4 * n * Sxx - 4 * Sx ** 2) > 0
    return {"m": m, "b": b, "pasos": pasos, "verificacion": "passed" if ok else "failed"}


def extremo_con_parametros(f_txt, vars_, punto, parametros, valor=None):
    """Valores de los parámetros para los que f tiene un extremo local en 'punto' (y, opcionalmente, vale 'valor')."""
    vars_ = list(vars_); params = list(parametros)
    f = X._P(f_txt)
    pt = {v: ast_num(F(c)) for v, c in zip(vars_, punto)}
    def en_punto(a):
        for v, c in pt.items(): a = ast_subs(a, v, c)
        return a
    ecs = [en_punto(X._d(f, v)) for v in vars_]
    pasos = [{"text": "Condición necesaria: el punto debe ser crítico (∇f = 0 en el punto)",
              "latex": r"\quad ".join(r"f_{%s}(%s) = 0" % (v, ",".join(str(c) for c in punto)) for v in vars_)}]
    if valor is not None:
        from ..ast_tools import mk_sub
        ecs.append(mk_sub(en_punto(f), ast_num(F(valor))))
        pasos.append({"text": "El valor de la función en el punto es el dado", "latex": r"f(%s) = %s" % (",".join(str(c) for c in punto), valor)})
    if len(ecs) != len(params):
        raise NoSoportado(f"Hay {len(ecs)} ecuaciones y {len(params)} parámetros: el sistema no queda determinado")
    sols = X.resolver_sistema(ecs, params)
    if len(sols) != 1: raise NoSoportado("El sistema de los parámetros no tiene solución única")
    sol = [X._reconocer(c) for c in sols[0]]
    pasos.append({"text": "Se resuelve para los parámetros", "latex": r",\; ".join("%s = %s" % (p, X._lat_coord(c)) for p, c in zip(params, sol))})
    # clasificación con los parámetros hallados
    sub = {p: ast_num(c) if isinstance(c, F) else ast_num(F(c).limit_denominator(10 ** 6)) for p, c in zip(params, sol)}
    f2 = f
    for p, c in sub.items(): f2 = ast_subs(f2, p, c)
    from ..ast_tools import to_str
    cl = X.extremos_locales(to_str(f2), vars_)
    mio = [p for p in cl["puntos"] if all(abs(X._valor_gp(a) - float(b)) < 1e-9 for a, b in zip(p["punto"], punto))]
    clase = mio[0]["clase"] if mio else "inconcluso"
    pasos.append({"text": "Clasificación del punto con los parámetros hallados (Hessiana): " + clase, "latex": None})
    return {"params": dict(zip(params, sol)), "clase": clase, "pasos": pasos}


def condicion_parametro(f_txt, vars_, punto, param, tipo="minimo"):
    """Valores de 'param' para los que el punto (crítico) es mínimo/máximo local (Sylvester sobre la Hessiana)."""
    vars_ = list(vars_)
    f = from_ast(X._P(f_txt))
    pasos = []
    G = [f.deriv(v) for v in vars_]
    ceros = []
    for v, g in zip(vars_, G):
        val = g
        for w, c in zip(vars_, punto): val = val.subs(w, Expr.of(GP.const(F(c))))
        ceros.append(val.is_zero())
    pasos.append({"text": "Primeras derivadas parciales evaluadas en el punto",
                  "latex": r"\quad ".join(r"f_{%s}(%s) = %s" % (v, ",".join(str(c) for c in punto), 0 if z else "≠0") for v, z in zip(vars_, ceros))})
    if not all(ceros): raise NoSoportado("El punto no es crítico para todos los valores del parámetro")
    n = len(vars_)
    H = [[G[i].deriv(vars_[j]) for j in range(n)] for i in range(n)]
    for i in range(n):
        for j in range(n):
            for w, c in zip(vars_, punto): H[i][j] = H[i][j].subs(w, Expr.of(GP.const(F(c))))
    pasos.append({"text": "Matriz Hessiana en el punto", "latex": r"H = \begin{pmatrix}" + r" \\ ".join(" & ".join(lat(H[i][j]) for j in range(n)) for i in range(n)) + r"\end{pmatrix}"})
    from .cambio import _det
    mins = [_det([[H[i][j] for j in range(k)] for i in range(k)]) for k in range(1, n + 1)]
    pasos.append({"text": "Menores principales (criterio de Sylvester)", "latex": r",\; ".join(r"\Delta_{%d} = %s" % (k + 1, lat(m)) for k, m in enumerate(mins))})
    fs = [(lambda t, m=m: m.eval({param: t})) for m in mins]
    # raíces de los menores (polinomios en el parámetro)
    from .curvas import _raices
    puntos = set()
    for m in mins:
        for r in _raices(lambda t, m=m: m.eval({param: t}), -1000.0, 1000.0, 20000): puntos.add(round(r, 9))
    cs = sorted(puntos)
    cand = [cs[0] - 1] + [(a + b) / 2 for a, b in zip(cs, cs[1:])] + [cs[-1] + 1] if cs else [0.0]
    sgn = (lambda k: 1) if tipo == "minimo" else (lambda k: (-1) ** (k + 1))
    ok = []
    for t in cand:
        vals = [f_(t) for f_ in fs]
        ok.append(all((v > 0 if sgn(k) > 0 else v < 0) for k, v in enumerate(vals)))
    # intervalos
    tramos = []
    bordes = [None] + cs + [None]
    for i, v in enumerate(ok):
        if v: tramos.append((bordes[i], bordes[i + 1]))
    def fr(x):
        q = F(x).limit_denominator(1000)
        return (str(q) if q.denominator == 1 else f"{q.numerator}/{q.denominator}") if abs(float(q) - x) < 1e-8 else f"{x:.6g}"
    txt = " o ".join((f"{param} > {fr(a)}" if b is None else (f"{param} < {fr(b)}" if a is None else f"{fr(a)} < {param} < {fr(b)}")) for a, b in tramos) or "ningún valor"
    pasos.append({"text": "Condición para " + ("mínimo local" if tipo == "minimo" else "máximo local") + " (todos los menores con el signo requerido)", "latex": None})
    pasos.append({"text": "Resultado", "latex": txt})
    return {"condicion": txt, "tramos": tramos, "pasos": pasos}
