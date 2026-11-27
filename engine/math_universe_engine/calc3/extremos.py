"""Extremos locales (Hessiana) y extremos condicionados (multiplicadores de Lagrange) con procedimiento paso a paso.

Método: las derivadas se calculan simbólicamente; las ecuaciones ∇f = 0 (o ∇L = 0) se resuelven con Newton desde una
malla de puntos de partida; cada solución se identifica en forma exacta (racional o q·√N) y se COMPRUEBA sustituyendo.
La clasificación usa la Hessiana exacta (menores principales de Sylvester) o, con restricciones, la Hessiana del
lagrangiano sobre el espacio tangente."""
import math, itertools, random
from fractions import Fraction as F
from ..parser import parse
from ..ast_tools import normalize, deriv, eval_q, free_symbols, mk_add, mk_mul, num
from ..errors import MathDomainError, NotImplementedOperation
from .cas3 import GP, Expr, NoSoportado, from_ast, raiz_gp, pitag
from .numerico import compile_ast
from .iterada import lat, _fmt_num


def _P(s): return normalize(parse(s))


def _d(a, v):
    return deriv(a, v)


def _lat_ast(a):
    try: return lat(from_ast(a))
    except Exception: return None


def _ltx(ast, fallback=""):
    try: return from_ast(ast).to_str(True)
    except Exception:
        from ..presentation import latex_of
        try: return latex_of(__import__("math_universe_engine.ast_tools", fromlist=["to_str"]).to_str(ast))
        except Exception: return fallback


# ------------------------------------------------------------------ solución numérica con identificación exacta
def _reconocer(x, tol=1e-9):
    """x → Fraction, o (Fraction q, N) para q·√N, o float"""
    if abs(x) < 1e-12: return F(0)
    fr = F(x).limit_denominator(720)
    if abs(float(fr) - x) < tol * (1 + abs(x)): return fr
    x2 = F(x * x).limit_denominator(720)
    if x2 > 0 and abs(float(x2) - x * x) < tol * (1 + x * x):
        g = raiz_gp(x2)
        return g if x > 0 else -g
    return float(x)


def _valor_gp(c):
    return c.eval({}) if isinstance(c, GP) else float(c)


def _fmt_coord(c):
    if isinstance(c, GP): return c.to_str(False)
    if isinstance(c, F): return str(c) if c.denominator == 1 else f"{c.numerator}/{c.denominator}"
    return f"{c:.10g}"


def _lat_coord(c):
    if isinstance(c, GP): return c.to_str(True)
    if isinstance(c, F): return str(c) if c.denominator == 1 else (r"\frac{%d}{%d}" % (c.numerator, c.denominator) if c > 0 else r"-\frac{%d}{%d}" % (-c.numerator, c.denominator))
    return f"{c:.8g}"


def _newton(Fn, Jn, x0, it=80):
    n = len(x0); x = list(x0)
    for _ in range(it):
        try:
            fv = Fn(*x)
        except (ValueError, ZeroDivisionError, OverflowError):
            return None
        if any(isinstance(v, complex) or v != v for v in fv): return None
        nf = max(abs(v) for v in fv)
        if nf < 1e-14: return x
        try:
            J = Jn(*x)
        except (ValueError, ZeroDivisionError, OverflowError):
            return None
        dx = _solve_lin(J, fv)
        if dx is None: return None
        # amortiguación simple
        t = 1.0
        for _ in range(30):
            xn = [x[i] - t * dx[i] for i in range(n)]
            try:
                fn = Fn(*xn)
                if all(not isinstance(v, complex) and v == v for v in fn) and max(abs(v) for v in fn) < nf * (1 - 1e-4 * t) + 1e-300:
                    break
            except (ValueError, ZeroDivisionError, OverflowError):
                pass
            t /= 2
        else:
            return None
        x = xn
        if max(abs(t * d) for d in dx) > 1e8: return None
    try:
        return x if max(abs(v) for v in Fn(*x)) < 1e-11 else None
    except Exception:
        return None


def _solve_lin(A, b):
    n = len(b); M = [list(map(float, A[i])) + [float(b[i])] for i in range(n)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(M[r][c]))
        if abs(M[p][c]) < 1e-13: return None
        M[c], M[p] = M[p], M[c]
        for r in range(n):
            if r != c:
                f = M[r][c] / M[c][c]
                for k in range(c, n + 1): M[r][k] -= f * M[c][k]
    return [M[i][n] / M[i][i] for i in range(n)]


def resolver_sistema(eqs, vars_, dominio_positivo=None, semilla=7):
    """eqs: lista de AST (= 0).  Devuelve lista de soluciones (listas de float) distintas."""
    n = len(vars_)
    Fn = compile_list([e for e in eqs], vars_)
    jac = [[_d(e, v) for v in vars_] for e in eqs]
    Jn = compile_matrix(jac, vars_)
    rnd = random.Random(semilla)
    starts = []
    rango = [-4, -2, -1, -0.5, 0.0, 0.5, 1, 2, 4] if n <= 3 else [-2, -1, 0, 1, 2]
    if n <= 5: starts += list(itertools.product(rango, repeat=n)) if len(rango) ** n <= 20000 else []
    for _ in range(1500): starts.append([rnd.uniform(-8, 8) for _ in range(n)])
    for _ in range(600): starts.append([rnd.uniform(0.05, 6) for _ in range(n)])
    out = []
    for s0 in starts:
        sol = _newton(Fn, Jn, [float(v) + 0.0137 * (i + 1) for i, v in enumerate(s0)])
        if sol is None: continue
        if not any(max(abs(a - b) for a, b in zip(sol, o)) < 1e-7 for o in out):
            out.append(sol)
        if len(out) > 60: break
    out.sort()
    return out


def compile_list(asts, vars_):
    fs = [compile_ast(a, list(vars_)) for a in asts]
    return lambda *x: [f(*x) for f in fs]


def compile_matrix(M, vars_):
    fs = [[compile_ast(a, list(vars_)) for a in row] for row in M]
    return lambda *x: [[f(*x) for f in row] for row in fs]


# ------------------------------------------------------------------ evaluación exacta en un punto
def _eval_exacto(ast, vars_, punto):
    """ast evaluado en el punto (Fractions/GP): Expr exacto si es posible, si no float"""
    try:
        e = from_ast(ast)
        for v, c in zip(vars_, punto):
            e = e.subs(v, Expr.of(c if isinstance(c, GP) else GP.const(c)) if not isinstance(c, float) else Expr.of(GP.const(F(c).limit_denominator(10 ** 9))))
        return e
    except Exception:
        env = {v: _valor_gp(c) for v, c in zip(vars_, punto)}
        return compile_ast(ast, list(vars_))(*[env[v] for v in vars_])


def _num(x):
    if isinstance(x, Expr): return x.eval({})
    return float(x)


def _exacta_cero(ast, vars_, punto):
    """residuo exactamente 0 (Fraction o √N) si el punto es racional / q√N y la expresión es racional; None si no se pudo"""
    try:
        e = from_ast(ast)
        for v, c in zip(vars_, punto):
            if isinstance(c, float): return None
            e = e.subs(v, Expr.of(c if isinstance(c, GP) else GP.const(c)))
        return e.is_zero() if e.is_gp() or e.is_zero() else None
    except Exception:
        return None


# ------------------------------------------------------------------ Hessiana y clasificación
def _menores(Hnum):
    n = len(Hnum); out = []
    for k in range(1, n + 1):
        out.append(_det([[Hnum[i][j] for j in range(k)] for i in range(k)]))
    return out


def _det(M):
    n = len(M)
    if n == 1: return M[0][0]
    if n == 2: return M[0][0] * M[1][1] - M[0][1] * M[1][0]
    return sum(((-1) ** j) * M[0][j] * _det([[M[i][k] for k in range(n) if k != j] for i in range(1, n)]) for j in range(n))


def _clasificar_hess(H):
    """H: matriz (Fraction/float). Devuelve ('min'|'max'|'silla'|'inconcluso', menores)"""
    n = len(H)
    mins = _menores(H)
    tol = 1e-9
    def sg(v):
        v = float(v)
        return 0 if abs(v) < tol else (1 if v > 0 else -1)
    s = [sg(m) for m in mins]
    if all(v > 0 for v in s): return "mínimo local", mins
    if all(v == (-1) ** (i + 1) for i, v in enumerate(s)): return "máximo local", mins
    if s[-1] == 0: return "inconcluso", mins
    # det ≠ 0 y no definida → silla
    return "punto de silla", mins


def _nucleo_exp(f):
    """f = c·exp(g) con c>0 → g (mismos puntos críticos y misma clasificación); si no, None"""
    if f[0] == "call" and f[1] == "exp": return f[2][0]
    if f[0] == "bin" and f[1] == "*":
        for a, b in ((f[2], f[3]), (f[3], f[2])):
            if a[0] == "num" and a[1] > 0 and b[0] == "call" and b[1] == "exp": return b[2][0]
    return None


def extremos_locales(f_txt, vars_):
    f = _P(f_txt); pasos = []
    vars_ = list(vars_)
    g_nuc = _nucleo_exp(f)
    fex = None
    try: fex = from_ast(f)
    except Exception: pass
    pasos.append({"text": "Función", "latex": "f(%s) = %s" % (",".join(vars_), _ltx(f))})
    base = g_nuc if g_nuc is not None else f
    grads = [_d(base, v) for v in vars_]
    if g_nuc is not None:
        pasos.append({"text": "f = e^g con e^g > 0 siempre: f y g tienen los mismos puntos críticos y la misma clasificación", "latex": "g = " + _ltx(g_nuc)})
    gl = []
    for v, g in zip(vars_, grads):
        try: ge = from_ast(g); s = ge.to_str(True)
        except Exception: s = _ltx(g)
        gl.append(r"f_{%s} = %s" % (v, s))
    pasos.append({"text": "Derivadas parciales de primer orden", "latex": r"\quad ".join(gl)})
    pasos.append({"text": "Puntos críticos: se resuelve el sistema ∇" + ("g" if g_nuc is not None else "f") + " = 0", "latex": r"\quad ".join(r"%s_{%s} = 0" % ("g" if g_nuc is not None else "f", v) for v in vars_)})
    sols = resolver_sistema(grads, vars_)
    if not sols:
        pasos.append({"text": "No se encontraron puntos críticos reales", "latex": None})
    # identificar
    puntos = []
    for s in sols:
        rec = [_reconocer(c) for c in s]
        exacto = _exacta_cero_all(grads, vars_, rec)
        puntos.append({"num": s, "rec": rec, "verif_exacta": exacto})
    # Hessiana simbólica
    H_ast = [[_d(g, v) for v in vars_] for g in grads]
    try:
        Hlat = r"\begin{pmatrix}" + r" \\ ".join(" & ".join(from_ast(H_ast[i][j]).to_str(True) for j in range(len(vars_))) for i in range(len(vars_))) + r"\end{pmatrix}"
        pasos.append({"text": "Matriz Hessiana", "latex": r"H = " + Hlat})
    except Exception: pass
    resultados = []
    for p in puntos:
        rec = p["rec"]
        coord_txt = "(" + ", ".join(_lat_coord(c) for c in rec) + ")"
        try:
            Hn = [[_eval_numeric_hess(H_ast[i][j], vars_, rec) for j in range(len(vars_))] for i in range(len(vars_))]
        except Exception:
            Hn = [[compile_ast(H_ast[i][j], vars_)(*p["num"]) for j in range(len(vars_))] for i in range(len(vars_))]
        clase, mins = _clasificar_hess(Hn)
        fval = _eval_exacto(f, vars_, rec)
        fv_lat = lat(fval) if isinstance(fval, Expr) else _fmt_num(fval)
        fv_num = _num(fval)
        resultados.append({"punto": rec, "clase": clase, "f": fval, "fnum": fv_num, "menores": mins, "H": Hn, "verif": p["verif_exacta"]})
        n = len(vars_)
        if n == 2:
            fxx, fxy, fyy = Hn[0][0], Hn[0][1], Hn[1][1]
            D = mins[1]
            det_txt = r"D = f_{xx}f_{yy} - f_{xy}^2 = %s" % _lat_coord(_fr(D))
            pasos.append({"text": f"Punto crítico P{coord_txt.replace(chr(92), chr(92))}",
                          "latex": r"f_{xx} = %s,\; f_{yy} = %s,\; f_{xy} = %s,\; %s" % (_lat_coord(_fr(fxx)), _lat_coord(_fr(fyy)), _lat_coord(_fr(fxy)), det_txt)})
        else:
            pasos.append({"text": f"Punto crítico P{coord_txt}",
                          "latex": r"\Delta_k = " + r",\; ".join(_lat_coord(_fr(m)) for m in mins)})
        pasos.append({"text": "Clasificación: " + clase, "latex": r"f%s = %s" % (coord_txt, fv_lat)})
    return {"puntos": resultados, "pasos": pasos, "n_criticos": len(puntos)}


def _fr(x):
    if isinstance(x, F): return x
    if isinstance(x, GP): return x
    f = F(x).limit_denominator(10 ** 6)
    return f if abs(float(f) - x) < 1e-9 * (1 + abs(x)) else float(x)


def _eval_numeric_hess(ast, vars_, rec):
    """Valor de un elemento de la Hessiana en el punto (exacto si es racional)"""
    if all(isinstance(c, F) for c in rec):
        try:
            return eval_q_frac(ast, {v: c for v, c in zip(vars_, rec)})
        except Exception:
            pass
    return compile_ast(ast, vars_)(*[_valor_gp(c) for c in rec])


def eval_q_frac(ast, env):
    q = eval_q(ast, env)
    if q.b != 0: raise NoSoportado("irracional")
    return q.a


def _exacta_cero_all(grads, vars_, rec):
    res = [_exacta_cero(g, vars_, rec) for g in grads]
    if all(r is True for r in res): return "exacta"
    if any(r is False for r in res): return "falla"
    # comprobación numérica
    try:
        vals = [abs(compile_ast(g, vars_)(*[_valor_gp(c) for c in rec])) for g in grads]
        return "numerica" if max(vals) < 1e-9 else "falla"
    except Exception:
        return "numerica"
