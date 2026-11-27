"""Multiplicadores de Lagrange con una o dos restricciones (formato de clase)."""
import math
from fractions import Fraction as F
from . import extremos as X
from .cas3 import GP, Expr, from_ast
from .iterada import lat, _fmt_num
from .numerico import compile_ast


def _lam_names(m): return ["lam", "mu", "nu"][:m] if m <= 3 else [f"lam{i}" for i in range(m)]


def lagrange(f_txt, restricciones, vars_, positivo=False):
    """restricciones: lista de textos 'g(x,y)=c'. Devuelve dict(puntos, pasos)."""
    vars_ = list(vars_); n = len(vars_); m = len(restricciones)
    f = X._P(f_txt)
    gs = []; cs = []
    for r in restricciones:
        l, rr = r.split("=")
        g = X._P(f"({l})-({rr})")
        gs.append(g)
    lam = _lam_names(m)
    allv = vars_ + lam
    pasos = [{"text": "Función objetivo y restricciones",
              "latex": r"f = %s;\quad " % X._ltx(f) + r";\quad ".join(r"g_{%d}: %s" % (k + 1, r.replace("*", "").replace("^", "^")) for k, r in enumerate(restricciones))}]
    LAM = {"lam": r"\lambda", "mu": r"\mu", "nu": r"\nu"}
    # lagrangiano: L = f - Σ λ_k g_k   (g_k ya viene como expresión = 0)
    from ..ast_tools import mk_sub, mk_mul
    L = f
    for k, g in enumerate(gs): L = mk_sub(L, mk_mul(("sym", lam[k]), g))
    pasos.append({"text": "Condición de Lagrange: ∇f = Σ λₖ ∇gₖ junto con las restricciones",
                  "latex": r"\nabla f = " + " + ".join(r"%s\,\nabla g_{%d}" % (LAM.get(lam[k], lam[k]), k + 1) for k in range(m))})
    eqs_txt = []
    eqs = []
    for v in vars_:
        e = X._d(L, v); eqs.append(e)
        try: eqs_txt.append(from_ast(X._d(f, v)).to_str(True) + " = " + " + ".join(
            r"%s\left(%s\right)" % (LAM.get(lam[k], lam[k]), from_ast(X._d(gs[k], v)).to_str(True)) for k in range(m)))
        except Exception: pass
    for k, g in enumerate(gs): eqs.append(X._d(L, lam[k]))
    if eqs_txt: pasos.append({"text": "Sistema de ecuaciones", "latex": r"\\ ".join(eqs_txt) + r"\\ " + r"\\ ".join(r.replace("*", "") for r in restricciones)})
    sols = X.resolver_sistema(eqs, allv)
    if positivo: sols = [s for s in sols if all(c > 0 for c in s[:n])]
    pts = []
    for s in sols:
        rec = [X._reconocer(c) for c in s]
        # el residuo se comprueba en f y g (excluyendo λ)
        res = max(abs(v) for v in compile_ast_list(eqs, allv)(*s))
        if res > 1e-8: continue
        verif = X._exacta_cero_all([g for g in gs], vars_, rec[:n])
        fv = X._eval_exacto(f, vars_, rec[:n])
        pts.append({"punto": rec[:n], "lam": rec[n:], "num": s[:n], "f": fv, "fnum": X._num(fv), "verif": verif})
    # clasificación con la Hessiana del lagrangiano sobre el espacio tangente
    Hf = [[X._d(X._d(f, a), b) for b in vars_] for a in vars_]
    Hg = [[[X._d(X._d(g, a), b) for b in vars_] for a in vars_] for g in gs]
    Jg = [[X._d(g, v) for v in vars_] for g in gs]
    cH = X.compile_matrix(Hf, vars_)
    cHg = [X.compile_matrix(h, vars_) for h in Hg]
    cJ = X.compile_matrix(Jg, vars_)
    for p in pts:
        x = p["num"]; lamv = [float(X._valor_gp(c)) for c in p["lam"]]
        H = cH(*x); HL = [row[:] for row in H]
        for k in range(m):
            Hk = cHg[k](*x)
            for i in range(n):
                for j in range(n): HL[i][j] -= lamv[k] * Hk[i][j]
        Z = _nucleo(cJ(*x), n)
        if not Z:
            p["clase"] = "aislado"; continue
        R = [[sum(Z[a][i] * HL[i][j] * Z[b][j] for i in range(n) for j in range(n)) for b in range(len(Z))] for a in range(len(Z))]
        clase, mins = X._clasificar_hess(R)
        p["clase"] = {"mínimo local": "mínimo restringido", "máximo local": "máximo restringido", "punto de silla": "punto de silla restringido", "inconcluso": "inconcluso"}[clase]
    if pts:
        vmax = max(p["fnum"] for p in pts); vmin = min(p["fnum"] for p in pts)
        for p in pts:
            if abs(vmax - vmin) < 1e-9 * (1 + abs(vmax)): p["abs"] = None; continue
            p["abs"] = "máximo" if abs(p["fnum"] - vmax) < 1e-9 * (1 + abs(vmax)) else ("mínimo" if abs(p["fnum"] - vmin) < 1e-9 * (1 + abs(vmin)) else None)
    for k, p in enumerate(pts):
        coord = "(" + ", ".join(X._lat_coord(c) for c in p["punto"]) + ")"
        lt = r",\; ".join("%s = %s" % (LAM.get(lam[i], lam[i]), X._lat_coord(c)) for i, c in enumerate(p["lam"]))
        fv = lat(p["f"]) if isinstance(p["f"], Expr) else _fmt_num(p["f"])
        pasos.append({"text": f"Punto crítico {k + 1}: {p.get('clase', '')}", "latex": r"P_{%d}%s,\; %s,\; f = %s" % (k + 1, coord, lt, fv)})
    if len(pts) > 1:
        pasos.append({"text": "Comparación de los valores de f en los puntos críticos (si la restricción es un conjunto cerrado y acotado, el mayor es el máximo absoluto y el menor el mínimo absoluto)",
                      "latex": r";\; ".join(r"f(P_{%d}) = %s" % (k + 1, _fmt_num(p["fnum"])) for k, p in enumerate(pts))})
    return {"puntos": pts, "pasos": pasos}


def compile_ast_list(asts, vars_):
    return X.compile_list(asts, vars_)


def _nucleo(J, n):
    """base del espacio nulo de J (filas) por eliminación; devuelve lista de vectores float"""
    A = [list(map(float, r)) for r in J]
    piv = []; r = 0
    for c in range(n):
        p = max(range(r, len(A)), key=lambda i: abs(A[i][c]), default=None)
        if p is None or abs(A[p][c]) < 1e-10: continue
        A[r], A[p] = A[p], A[r]
        pv = A[r][c]; A[r] = [v / pv for v in A[r]]
        for i in range(len(A)):
            if i != r:
                f = A[i][c]; A[i] = [a - f * b for a, b in zip(A[i], A[r])]
        piv.append(c); r += 1
        if r == len(A): break
    libres = [c for c in range(n) if c not in piv]
    base = []
    for lc in libres:
        v = [0.0] * n; v[lc] = 1.0
        for i, pc in enumerate(piv): v[pc] = -A[i][lc]
        base.append(v)
    return base
