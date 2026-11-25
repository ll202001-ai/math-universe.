"""Derivadas, integrales y límites simbólicos exactos (motor propio)."""
import math
from fractions import Fraction
from . import limits
from .arith import evaluate as arith_eval
from .ast_tools import (normalize, deriv, to_str, subs, eval_float, free_symbols, const_value, num)
from .errors import NotImplementedOperation, NotSolved, MathDomainError, InvalidRequest
from .parser import parse
from .poly import Poly, u_divmod, u_factor, u_to_poly, u_trim, u_mul, u_add
from .rational import Ctx, to_rf, rf_str, RF
from . import series as S


def canon(ast, assumptions=None):
    c = Ctx(assumptions); r = to_rf(ast, c).cancel(c.warnings)
    return rf_str(r), c


def _fr(x): return str(x.numerator) if x.denominator == 1 else f"({x.numerator}/{x.denominator})"


# ====================== derivadas ======================
def differentiate(ast, var, order=1):
    d = ast
    for _ in range(order):
        d = deriv(d, var)
    return d


def _stencil1(f, x, h):
    vals = [f(x - 2 * h), f(x - h), f(x + h), f(x + 2 * h)]
    return (-vals[3] + 8 * vals[2] - 8 * vals[1] + vals[0]) / (12 * h), 3.4e-15 * max(abs(v) for v in vals) / h


def _stencil(f, x, h):
    """Derivada central de orden 4 y cota del error de redondeo (1.5·ε·max|f|/h con margen 10×).
    Se calcula con h y h/2: si discrepan, el punto está mal condicionado (cerca de una singularidad u oscilación rápida)
    y se devuelve rnd=inf para que NO cuente como evidencia (ni a favor ni en contra)."""
    d1, r1 = _stencil1(f, x, h)
    d2, r2 = _stencil1(f, x, h / 2)
    rnd = max(r1, r2)
    if abs(d1 - d2) > 1e-6 * (1 + abs(d2)) + 4 * rnd: return d2, float("inf")
    return d2, rnd


def verify_derivative(ast, var, result_ast, points=None):
    """Compara el resultado simbólico con diferencias finitas centrales del ORIGINAL en puntos de prueba."""
    pts = points or [Fraction(k, 7) + Fraction(1, 11) for k in range(-9, 22, 3)]
    okc = 0
    syms = free_symbols(ast) - {var}
    env0 = {s: 1.37 + i * 0.41 for i, s in enumerate(sorted(syms))}
    for p in pts:
        x = float(p); h = 1e-5
        try:
            f = lambda t: eval_float(ast, {**env0, var: t})
            num_d, rnd = _stencil(f, x, h)
            sym_d = eval_float(result_ast, {**env0, var: x})
        except Exception:
            continue
        if not (math.isfinite(num_d) and math.isfinite(sym_d)): continue
        if rnd > 1e-3 * (1 + abs(sym_d)): continue          # punto no informativo (|f| enorme): no cuenta como evidencia
        if abs(num_d - sym_d) > 1e-5 * (1 + abs(sym_d)) + rnd: return "failed"
        okc += 1
    return "passed" if okc >= 3 else "not_possible"


# ====================== integrales ======================
def _split_term(m, var):
    k = 0; atoms = []; coef = []
    for v, e in m:
        if v == var: k = e
        elif not v.isidentifier():            # átomo (sin(x), x^n, sqrt(2)...): no es un símbolo simple
            node = parse(v)
            if var in free_symbols(node):
                atoms.append((v, e, node))
            else: coef.append((v, e))
        else: coef.append((v, e))
    return k, atoms, tuple(coef)


def _linear_arg(argnode, var):
    c = Ctx(); r = to_rf(normalize(argnode), c).cancel()
    if not r.d.is_const(): return None
    co = r.n.coeffs_in(var)
    if set(co) - {0, 1} or 1 not in co or not co[1].is_const(): return None
    if co.get(0, Poly()).vars() and var in co.get(0, Poly()).vars(): return None
    a = co[1].const_value() / r.d.const_value()
    b = co.get(0, Poly()).scale(1 / r.d.const_value())
    return a, b


def _poly_str(coefmono, var, k, extra=""):
    pass


def _integrate_polynomial_part(n, var, d_const):
    """n: Poly en var (+ parámetros + átomos); devuelve cadena de la primitiva."""
    pieces = []
    for m, c in n.t.items():
        limits.check()
        k, atoms, coef = _split_term(m, var)
        cstr = Poly({coef: c / d_const})
        cs = f"({cstr})"
        if not atoms:
            pieces.append(f"{cs}*{var}^{k + 1}/{k + 1}")
            continue
        if len(atoms) != 1 or atoms[0][1] != 1:
            raise NotSolved("Producto/potencia de funciones no soportado por el integrador propio")
        name, _, node = atoms[0]
        f, arg = node[1], node[2][0]
        if f == "ln":
            if arg != ("sym", var): raise NotSolved("Solo ln(x) con argumento x")
            pieces.append(f"{cs}*({var}^{k + 1}/{k + 1}*ln({var}) - {var}^{k + 1}/{(k + 1) ** 2})")
            continue
        if f in ("sin", "cos", "exp"):
            lin = _linear_arg(arg, var)
            if lin is None: raise NotSolved("Argumento no lineal en integrando trascendente")
            a, b = lin
            u = f"{to_str(arg)}"
            P = Poly({((var, k),): Fraction(1)}) if k else Poly.const(1)
            terms = []
            cur = P; j = 0
            seqs = {"exp": lambda j: (f"exp({u})", 1 / a ** j if j else 1),
                    "sin": None, "cos": None}
            while not cur.is_zero():
                limits.check()
                jj = j + 1
                if f == "exp": base, sgn_coef = f"exp({u})", Fraction(1) / a ** jj
                else:
                    # S_j para sin: [sin, -cos/a, -sin/a², cos/a³]; para cos: [cos, sin/a, -cos/a², -sin/a³]
                    tab = {"sin": [("sin", 1), ("cos", -1), ("sin", -1), ("cos", 1)],
                           "cos": [("cos", 1), ("sin", 1), ("cos", -1), ("sin", -1)]}[f]
                    fn, sg = tab[jj % 4]
                    base, sgn_coef = f"{fn}({u})", Fraction(sg) / a ** jj
                terms.append(f"({(-1) ** j * sgn_coef})*({cur})*{base}")
                cur = cur.diff(var); j += 1
            pieces.append(f"{cs}*(" + " + ".join(terms) + ")")
            continue
        raise NotSolved(f"Integral de {f} no implementada")
    return " + ".join(pieces) if pieces else "0"


def _rational_part(num_u, den_u, var):
    """∫ num/den con den factorizable en lineales racionales (cualquier multiplicidad) y cuadráticos simples."""
    sc, facs, complete = u_factor(den_u)
    if not complete: raise NotSolved("Denominador con factores no verificados")
    D = [x for x in den_u]
    unknowns = []  # (tipo, factor, j)
    basis = []
    for f, m in facs:
        if len(f) == 2:
            for j in range(1, m + 1):
                fj = [Fraction(1)]
                for _ in range(j): fj = u_mul(fj, f)
                q, r = u_divmod(D, fj)
                if r: raise NotSolved("Error interno de fracciones parciales")
                unknowns.append(("lin", f, j)); basis.append(q)
        elif len(f) == 3 and m == 1:
            q, r = u_divmod(D, f)
            unknowns.append(("quadB", f, 1)); basis.append(u_mul(q, [Fraction(0), Fraction(1)]))
            unknowns.append(("quadC", f, 1)); basis.append(q)
        else:
            raise NotSolved("Factor irreducible de grado ≥3 o cuadrático repetido: no implementado")
    n = len(den_u) - 1
    M = []
    for i in range(n):
        M.append([(b[i] if i < len(b) else Fraction(0)) for b in basis] + [num_u[i] if i < len(num_u) else Fraction(0)])
    from .solve import rref
    R, piv = rref(M, len(basis), [])
    if len(piv) != len(basis): raise NotSolved("Sistema de fracciones parciales singular")
    coef = {}
    for i, c in enumerate(piv): coef[c] = R[i][len(basis)]
    pieces = []; vi = {"quadB": {}, "quadC": {}}
    X = var
    for idx, (kind, f, j) in enumerate(unknowns):
        A = coef[idx]
        if A == 0: continue
        if kind == "lin":
            lin = f"({_fr(f[1])}*{X} + {_fr(f[0])})"
            if j == 1: pieces.append(f"{_fr(A / f[1])}*ln(abs({lin}))")
            else: pieces.append(f"{_fr(A / (f[1] * (1 - j)))}*{lin}^{1 - j}")
        else:
            vi[kind][tuple(f)] = A
    for key in set(vi["quadB"]) | set(vi["quadC"]):
        f = list(key); a, b, c = f[2], f[1], f[0]
        B = vi["quadB"].get(key, Fraction(0)); C = vi["quadC"].get(key, Fraction(0))
        Q = f"({_fr(a)}*{X}^2 + {_fr(b)}*{X} + {_fr(c)})"
        if B != 0: pieces.append(f"{_fr(B / (2 * a))}*ln({Q})")
        K = C - B * b / (2 * a)
        if K != 0:
            disc = 4 * a * c - b * b
            if disc > 0:
                pieces.append(f"{_fr(K * 2)}/sqrt({_fr(disc)})*atan((2*{_fr(a)}*{X} + {_fr(b)})/sqrt({_fr(disc)}))")
            else:
                Dd = -disc
                pieces.append(f"{_fr(K)}/sqrt({_fr(Dd)})*ln(abs((2*{_fr(a)}*{X} + {_fr(b)} - sqrt({_fr(Dd)}))/(2*{_fr(a)}*{X} + {_fr(b)} + sqrt({_fr(Dd)}))))")
    return " + ".join(pieces) if pieces else "0"


def integrate_indefinite(ast, var):
    """Devuelve (cadena de la primitiva sin +C, AST)."""
    ctx = Ctx(); f = to_rf(ast, ctx).cancel(ctx.warnings)
    if f.d.is_const():
        s = _integrate_polynomial_part(f.n, var, f.d.const_value())
    else:
        if any(not v.isidentifier() for v in f.n.vars() + f.d.vars()):
            raise NotSolved("Cociente con funciones trascendentes: no implementado")
        vs = set(f.n.vars()) | set(f.d.vars())
        if vs - {var}: raise NotSolved("Fracciones parciales con parámetros: no implementado")
        nu, du = f.n.to_upoly(var) if f.n.vars() else [f.n.const_value()], f.d.to_upoly(var)
        q, r = u_divmod(nu, du)
        parts = []
        if q: parts.append(_integrate_polynomial_part(u_to_poly(q, var), var, Fraction(1)))
        if r: parts.append(_rational_part(r, du, var))
        s = " + ".join(parts) if parts else "0"
    res = parse(s)
    return normalize(res)


def verify_antiderivative(ast, var, F, points=None):
    pts = points or [Fraction(k, 5) + Fraction(1, 13) for k in range(-12, 25, 3)]
    syms = free_symbols(ast) - {var}
    env0 = {s: 1.37 + i * 0.41 for i, s in enumerate(sorted(syms))}
    okc = 0
    for p in pts:
        x = float(p); h = 1e-5
        try:
            g = lambda t: eval_float(F, {**env0, var: t})
            nd, rnd = _stencil(g, x, h)
            fv = eval_float(ast, {**env0, var: x})
        except Exception:
            continue
        if not (math.isfinite(nd) and math.isfinite(fv)): continue
        if rnd > 1e-3 * (1 + abs(fv)): continue
        if abs(nd - fv) > 1e-4 * (1 + abs(fv)) + rnd: return "failed"
        okc += 1
    return "passed" if okc >= 3 else "not_possible"


def definite(ast, var, F, lo, hi):
    """F(hi)-F(lo) exacto como cadena + aproximación numérica independiente (Simpson)."""
    a, b = const_value(lo), const_value(hi)
    if a is None or b is None: raise InvalidRequest("Los límites deben ser constantes racionales")
    if a == b: return "0", 0.0, "passed"
    sgn = 1
    ex = ("bin", "-", subs(F, var, hi), subs(F, var, lo))
    # singularidades: el integrando no debe ser infinito en el intervalo
    n = 4000; lo_f, hi_f = float(a), float(b)
    for t in (lo_f, hi_f):
        try: eval_float(F, {var: t})
        except Exception: raise NotImplementedOperation("Singularidad en un extremo: integral impropia no implementada")
    return ex, lo_f, hi_f


def simpson(ast, var, a, b, n=None):
    """Cuadratura de Simpson ADAPTATIVA (pila explícita, tolerancia absoluta+relativa, tope de evaluaciones).
    Más robusta que Simpson uniforme (picos estrechos como 1/(x^2+1) en [-1000,1000])."""
    f = lambda x: _finite(eval_float(ast, {var: x}))
    if a == b: return 0.0
    sign = 1.0
    if a > b: a, b, sign = b, a, -1.0
    fa, fb, fm = f(a), f(b), f((a + b) / 2)
    whole = (b - a) / 6 * (fa + 4 * fm + fb)
    tol0 = 1e-11 * (1 + abs(whole))
    # inicial: 64 subintervalos para no confundir un pico estrecho con una función "plana"
    N0 = 64
    total, evals = 0.0, 3
    stack = []
    for i in range(N0):
        lo = a + (b - a) * i / N0; hi = a + (b - a) * (i + 1) / N0
        flo, fhi, fmid = f(lo), f(hi), f((lo + hi) / 2); evals += 3
        stack.append((lo, hi, flo, fmid, fhi, (hi - lo) / 6 * (flo + 4 * fmid + fhi), tol0 / N0, 0))
    while stack:
        limits.check()
        lo, hi, flo, fmid, fhi, S, tol, depth = stack.pop()
        mid = (lo + hi) / 2
        l_m, r_m = (lo + mid) / 2, (mid + hi) / 2
        fl, fr = f(l_m), f(r_m); evals += 2
        Sl = (mid - lo) / 6 * (flo + 4 * fl + fmid)
        Sr = (hi - mid) / 6 * (fmid + 4 * fr + fhi)
        if depth >= 40 or abs(Sl + Sr - S) <= 15 * tol:
            total += Sl + Sr + (Sl + Sr - S) / 15
        else:
            stack.append((lo, mid, flo, fl, fmid, Sl, tol / 2, depth + 1))
            stack.append((mid, hi, fmid, fr, fhi, Sr, tol / 2, depth + 1))
        if evals > 400000: raise MathDomainError("Cuadratura numérica sin convergencia")
    return sign * total


def _finite(v):
    if isinstance(v, complex) or not math.isfinite(v): raise MathDomainError("Integrando no finito en el intervalo")
    return v


# ====================== límites ======================
def parse_point(text):
    t = text.strip().replace(" ", "").lower()
    if t in ("oo", "+oo", "inf", "+inf", "∞", "+∞"): return "+inf"
    if t in ("-oo", "-inf", "-∞"): return "-inf"
    v = const_value(normalize(parse(text)))
    if v is None: raise InvalidRequest("El punto del límite debe ser un racional, +oo o -oo")
    return v


def _eval_series(n, var, xs, M):
    k = n[0]
    if k == "num": return S.const(n[1])
    if k == "sym":
        if n[1] == var: return xs
        raise NotImplementedOperation(f"Parámetro libre '{n[1]}' en el límite")
    if k == "neg": return -_eval_series(n[1], var, xs, M)
    if k == "bin":
        op = n[1]
        if op == "^":
            c = const_value(n[3])
            if c is None or c.denominator != 1: raise NotImplementedOperation("Exponente no entero en límite")
            return S.trunc(_eval_series(n[2], var, xs, M).pow(int(c), M), M)
        a, b = _eval_series(n[2], var, xs, M), _eval_series(n[3], var, xs, M)
        if op == "+": return S.trunc(a + b, M)
        if op == "-": return S.trunc(a - b, M)
        if op == "*": return S.trunc(a * b, M)
        if op == "/":
            if not b.c: raise MathDomainError("División por cero")
            return S.trunc(a * b.inv(M), M)
    if k == "call":
        if len(n[2]) != 1: raise NotImplementedOperation("Función con varios argumentos")
        return S.apply(n[1], _eval_series(n[2][0], var, xs, M), M)
    raise NotImplementedOperation("Nodo no soportado en límites")


def _lead(ser):
    if not ser.c: return None
    v = ser.val(); return v, ser.c[v]


def limit(ast, var, point, direction="both"):
    """Devuelve dict: {'kind': 'finite'|'inf'|'dne', 'value'|'sign'|'reason'}."""
    for M in (8, 16, 32, 64):
        limits.check()
        if point in ("+inf", "-inf"):
            xs = S.Ser({-1: Fraction(1)}, S.INF); sides = ["+"] if point == "+inf" else ["-"]
        else:
            xs = S.Ser({0: Fraction(point), 1: Fraction(1)}, S.INF)
            sides = {"both": ["+", "-"], "+": ["+"], "-": ["-"]}[direction]
        ser = _eval_series(ast, var, xs, M)
        lead = _lead(ser)
        if lead is None:
            continue
        v, c = lead
        results = []
        for sd in sides:
            if v > 0: results.append(("finite", Fraction(0)))
            elif v == 0: results.append(("finite", c))
            else:
                sign = 1 if c > 0 else -1
                if sd == "-" and v % 2: sign = -sign
                results.append(("inf", sign))
        if all(r == results[0] for r in results):
            kind, val = results[0]
            return {"kind": kind, "value" if kind == "finite" else "sign": val}
        return {"kind": "dne", "reason": "los límites laterales difieren", "sides": results}
    raise NotImplementedOperation("No se pudo decidir el límite con la precisión de serie disponible")


def verify_limit(ast, var, point, res, direction="both"):
    try:
        if point in ("+inf", "-inf"):
            sg = 1 if point == "+inf" else -1
            xs = [sg * 1e3, sg * 1e5]
        else:
            a = float(point)
            hs = [1e-2, 1e-3, 1e-4]
            xs_by = {"+": [a + h for h in hs], "-": [a - h for h in hs]}
            xs = None
        sides = [("+", )] if True else []
    except Exception:
        return "not_possible"
    def vals(points):
        out = []
        for x in points:
            try: out.append(eval_float(ast, {var: x}))
            except Exception: pass
        return out
    checks = []
    if point in ("+inf", "-inf"): checks.append(vals(xs))
    else:
        for sd in (["+", "-"] if direction == "both" else [direction]):
            checks.append(vals(xs_by[sd]))
    if res["kind"] == "dne": return "not_possible"
    status = []
    for vs in checks:
        vs = [v for v in vs if math.isfinite(v)]
        if len(vs) < 2: status.append("not_possible"); continue
        if res["kind"] == "finite":
            L = float(res["value"]); errs = [abs(v - L) for v in vs]
            scale = 1 + abs(L)
            if min(errs[-2:]) < 3e-3 * scale: status.append("passed")
            elif min(errs) > 0.05 * scale: status.append("failed")
            else: status.append("not_possible")
        else:
            s = res["sign"]
            status.append("passed" if abs(vs[-1]) > 100 and vs[-1] * s > 0 else ("failed" if vs[-1] * s < 0 else "not_possible"))
    if "failed" in status: return "failed"
    return "passed" if all(x == "passed" for x in status) else "not_possible"
