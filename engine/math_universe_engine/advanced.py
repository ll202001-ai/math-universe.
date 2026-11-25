"""Matemáticas avanzadas (motor 0.6.0, contrato 1.2).

Cálculo con SymPy cuando el motor propio no cubre la rama; CADA resultado pasa por una comprobación independiente del
algoritmo que lo produjo (otra biblioteca, otra vía de cálculo o evaluación numérica en puntos de prueba). Si la
comprobación no es posible se declara `not_possible`; si falla, el resultado no se entrega (VERIFICATION_FAILED).

Operaciones: eigen, partial, gradient, hessian, jacobian, series, inequality, complex, ode, laplace, inverse_laplace,
stats, units, formula.
"""
import cmath
import math
import random
import re
import statistics
from fractions import Fraction

from . import symbolic
from .ast_tools import normalize, free_symbols
from .errors import (InvalidRequest, MathDomainError, NotImplementedOperation, NotSolved, ParseError,
                     DependencyMissing)
from .parser import parse

ADVANCED_OPS = ("eigen", "partial", "gradient", "hessian", "jacobian", "series", "inequality", "complex", "ode",
                "laplace", "inverse_laplace", "stats", "units", "formula")

MAX_EIGEN_N = 6


def _sp():
    if symbolic.sp is None:
        raise DependencyMissing("SymPy no está disponible en este entorno", {"package": "sympy"})
    return symbolic.sp


def _ast(text):
    return normalize(parse(text))


def _S(text):
    return symbolic.to_sympy(_ast(text))


def _txt(e):
    return symbolic.from_sympy_text(str(e))


def _latex(e):
    try:
        return _sp().latex(e)
    except Exception:
        return None


def _res(exact, method, ver, data=None, approx=None, latex=None, conditions=None, status="success_exact"):
    out = {"status": status, "exact_result": exact, "approximate_result": approx, "method": method,
           "verification": {"status": ver[0], "method": ver[1]}, "data": data or {}}
    if latex is not None: out["latex"] = {"result": latex}
    if conditions: out["conditions_extra"] = conditions
    return out


def _check(ok, what):
    from .errors import VerificationFailed
    if ok is False:
        raise VerificationFailed("La verificación independiente falló: el resultado no se entrega como válido", {"method": what})


def _num(expr, subs, dps=30):
    """Valor numérico complejo de una expresión SymPy en un punto (None si no está definida)."""
    sp = _sp()
    try:
        v = expr.subs(subs).doit()
        v = sp.N(v, dps)
        if v.has(sp.zoo, sp.nan, sp.oo, -sp.oo) or v.free_symbols: return None
        return complex(v)
    except Exception:
        return None


def _close(a, b, tol=1e-9):
    if a is None or b is None: return False
    return abs(a - b) <= tol * max(1.0, abs(a), abs(b))


def _points(symbols, k=4, seed=7):
    rnd = random.Random(seed)
    pts = []
    for _ in range(k * 3):
        pts.append({s: _sp().Rational(rnd.randint(-19, 19), rnd.randint(3, 9)) for s in symbols})
    return pts


# ------------------------------------------------------------------ álgebra lineal: autovalores
def op_eigen(req, st, matrix_text):
    sp = _sp()
    rows = matrix_text
    M = sp.Matrix([[_S(str(c)) for c in r] for r in rows])
    n = M.rows
    if M.rows != M.cols: raise InvalidRequest("La matriz debe ser cuadrada para calcular autovalores")
    if n > MAX_EIGEN_N: raise InvalidRequest(f"Autovalores exactos: máximo {MAX_EIGEN_N}×{MAX_EIGEN_N}")
    if M.free_symbols: raise InvalidRequest("Autovalores: la matriz debe ser numérica")
    lam = sp.Symbol("lambda")
    p = M.charpoly(lam).as_expr()
    vects = M.eigenvects()
    # verificación independiente: A·v = λ·v exacto; Σ mult = n; Σ λ·mult = traza (de las entradas); Π λ^mult = det (Bareiss)
    ok = True
    total = 0
    tr = 0
    pr = 1
    for val, mult, vs in vects:
        total += mult
        tr += val * mult
        pr *= val ** mult
        for v in vs:
            if sp.simplify(M * v - val * v) != sp.zeros(n, 1): ok = False
    ok = ok and total == n and sp.simplify(tr - sum(M[i, i] for i in range(n))) == 0 \
        and sp.simplify(pr - M.det(method="bareiss")) == 0
    _check(ok, "A·v = λ·v y traza/determinante")
    vals = []
    parts = []
    for val, mult, vs in vects:
        vtxt = [[_txt(sp.nsimplify(x)) for x in v] for v in vs]
        vals.append({"value": _txt(val), "latex": _latex(val), "multiplicity": int(mult), "vectors": vtxt,
                     "approximate": _fmt(_num(val, {}))})
        parts.append(f"λ = {_txt(val)} (multiplicidad {mult}): " + "; ".join("[" + ", ".join(v) + "]" for v in vtxt))
    diag = all(len(vs) == m for _, m, vs in vects)
    lat = r",\quad ".join(r"\lambda = " + _latex(v) for v, _, _ in vects)
    return _res(" | ".join(parts), "sympy_eigenvects_verificado", ("passed", "A·v = λ·v exacto, Σλ = traza, Πλ = det"),
                data={"eigenvalues": vals, "characteristic_polynomial": _txt(sp.expand(p)),
                      "characteristic_polynomial_latex": _latex(sp.expand(p)), "diagonalizable": diag}, latex=lat)


def _fmt(z):
    if z is None: return None
    if abs(z.imag) < 1e-14: return format(z.real, ".15g")
    return f"{z.real:.15g} {'+' if z.imag >= 0 else '-'} {abs(z.imag):.15g}*i"


# ------------------------------------------------------------------ cálculo multivariable
def _vars(expr, req):
    names = req.get("variables")
    sp = _sp()
    if names: return [sp.Symbol(v) for v in names]
    return sorted(expr.free_symbols, key=lambda s: s.name)


def _fd_ok(expr, symbol_list, d_exact, derivs, k=3):
    """Contraste numérico con diferencias finitas centrales (mpmath, alta precisión) en puntos racionales."""
    import mpmath
    sp = _sp()
    good = 0
    for pt in _points(symbol_list, k):
        f = sp.lambdify(symbol_list, expr, "mpmath")
        try:
            mpmath.mp.dps = 40
            h = mpmath.mpf("1e-12")
            args = [mpmath.mpf(pt[s].p) / pt[s].q for s in symbol_list]
            num = _nderiv(f, args, derivs, symbol_list, h)
            ex = _num(d_exact, pt, 30)
            if ex is None or num is None: continue
            if abs(ex - complex(num)) > 1e-7 * max(1, abs(ex)): return False
            good += 1
            if good >= k: return True
        except Exception:
            continue
    return None if good == 0 else True


def _nderiv(f, args, derivs, syms, h):
    import mpmath
    idx = [syms.index(d) for d in derivs]
    orders = [idx.count(i) for i in range(len(args))]
    return mpmath.diff(lambda *a: f(*a), args, tuple(orders))


def op_partial(req, st):
    sp = _sp()
    expr = _S(req["expression"])
    vs = req.get("variables") or []
    if not vs: raise InvalidRequest("Indique las variables de derivación en orden, p. ej. variables = [x, y] para ∂²f/∂x∂y")
    syms = sorted(expr.free_symbols | {sp.Symbol(v) for v in vs}, key=lambda s: s.name)
    d = sp.diff(expr, *[sp.Symbol(v) for v in vs])
    d = sp.simplify(d)
    ok = _fd_ok(expr, syms, d, [sp.Symbol(v) for v in vs])
    _check(ok, "diferencias finitas")
    num = "".join(r"\partial " + v for v in vs)
    lat = r"\frac{\partial^{%d} f}{%s} = %s" % (len(vs), num, _latex(d)) if len(vs) > 1 else \
        r"\frac{\partial f}{\partial %s} = %s" % (vs[0], _latex(d))
    return _res(_txt(d), "sympy_diff_parcial", (("passed" if ok else "not_possible"), "diferencias finitas de alta precisión" if ok else None),
                latex=lat)


def op_gradient(req, st):
    sp = _sp()
    expr = _S(req["expression"])
    xs = _vars(expr, req)
    g = [sp.simplify(sp.diff(expr, x)) for x in xs]
    oks = [_fd_ok(expr, xs, gi, [x]) for gi, x in zip(g, xs)]
    for o in oks: _check(o, "diferencias finitas")
    ok = all(o is True for o in oks)
    lat = r"\nabla f = \left(" + ",\\ ".join(_latex(c) for c in g) + r"\right)"
    return _res("(" + ", ".join(_txt(c) for c in g) + ")", "sympy_gradiente",
                ("passed" if ok else "not_possible", "diferencias finitas de alta precisión" if ok else None),
                data={"variables": [str(x) for x in xs], "components": [_txt(c) for c in g]}, latex=lat)


def op_hessian(req, st):
    sp = _sp()
    expr = _S(req["expression"])
    xs = _vars(expr, req)
    H = sp.hessian(expr, xs).applyfunc(sp.simplify)
    ok = True
    for i, xi in enumerate(xs):
        for j, xj in enumerate(xs):
            if j < i: continue
            o = _fd_ok(expr, xs, H[i, j], [xi, xj], k=2)
            _check(o, "diferencias finitas")
            ok = ok and o is True
    txt = "[[" + "], [".join(", ".join(_txt(H[i, j]) for j in range(len(xs))) for i in range(len(xs))) + "]]"
    data = {"variables": [str(x) for x in xs], "matrix": [[_txt(H[i, j]) for j in range(len(xs))] for i in range(len(xs))]}
    try:
        data["determinant"] = _txt(sp.simplify(H.det()))
    except Exception:
        pass
    return _res(txt, "sympy_hessiano", ("passed" if ok else "not_possible", "diferencias finitas de alta precisión" if ok else None),
                data=data, latex=r"H = " + _latex(H))


def op_jacobian(req, st):
    sp = _sp()
    comps = [c.strip() for c in re.split(r"[;\n]", req["expression"]) if c.strip()]
    F = [_S(c) for c in comps]
    xs = [sp.Symbol(v) for v in req["variables"]] if req.get("variables") else \
        sorted(set().union(*[f.free_symbols for f in F]), key=lambda s: s.name)
    J = sp.Matrix([[sp.simplify(sp.diff(f, x)) for x in xs] for f in F])
    ok = True
    for i, f in enumerate(F):
        for j, x in enumerate(xs):
            o = _fd_ok(f, xs, J[i, j], [x], k=2)
            _check(o, "diferencias finitas")
            ok = ok and o is True
    data = {"variables": [str(x) for x in xs], "matrix": [[_txt(J[i, j]) for j in range(len(xs))] for i in range(len(F))]}
    if J.rows == J.cols:
        data["determinant"] = _txt(sp.simplify(J.det()))
    txt = "[[" + "], [".join(", ".join(row) for row in data["matrix"]) + "]]"
    return _res(txt, "sympy_jacobiano", ("passed" if ok else "not_possible", "diferencias finitas de alta precisión" if ok else None),
                data=data, latex=r"J = " + _latex(J))


# ------------------------------------------------------------------ series de Taylor
def op_series(req, st):
    sp = _sp()
    import mpmath
    expr = _S(req["expression"])
    xs = _vars(expr, req)
    if len(xs) != 1: raise InvalidRequest("Series: indique una sola variable")
    x = xs[0]
    p = _S(req.get("point") or "0")
    n = int(req.get("order") or 6)
    T = sp.series(expr, x, p, n).removeO()
    if T.has(sp.O) or not T.is_polynomial(x - p) and not T.has(x):
        pass
    # verificación numérica independiente: el error f(p+h) - T(p+h) debe decrecer como h^n (mpmath, 60 cifras)
    mpmath.mp.dps = 60
    f = sp.lambdify(x, expr, "mpmath")
    t = sp.lambdify(x, T, "mpmath")
    pv = mpmath.mpf(str(sp.N(p, 70)))
    ok = None
    try:
        errs = []
        for h in (mpmath.mpf("1e-3"), mpmath.mpf("5e-4")):
            errs.append(abs(f(pv + h) - t(pv + h)))
        if errs[0] < mpmath.mpf("1e-50"):
            ok = True                                      # coincide exactamente (p. ej. polinomios)
        else:
            ratio = errs[0] / errs[1]
            ok = bool(ratio > 2 ** (n - 0.5)) and bool(errs[0] < 10 ** (-3 * (n - 1) + 2))
    except Exception:
        ok = None
    _check(ok, "orden del error")
    lat = _latex(T) + r" + O\left(" + _latex((x - p) ** n) + r"\right)"
    return _res(_txt(T), "sympy_series_taylor",
                ("passed" if ok else "not_possible", f"el error f−T decrece como h^{n} (mpmath, 60 cifras)" if ok else None),
                data={"point": _txt(p), "order": n}, latex=lat)


# ------------------------------------------------------------------ inecuaciones
_REL = re.compile(r"(<=|>=|≤|≥|<|>)")


def op_inequality(req, st):
    sp = _sp()
    text = req["expression"].replace("≤", "<=").replace("≥", ">=")
    parts = _REL.split(text)
    if len(parts) != 3: raise ParseError("Escriba una sola desigualdad, p. ej. x^2 - 5x + 6 > 0")
    lhs, rel, rhs = parts
    a, b = _S(lhs), _S(rhs)
    xs = sorted((a - b).free_symbols, key=lambda s: s.name)
    if len(xs) != 1: raise InvalidRequest("Inecuaciones: una sola incógnita real")
    x = xs[0]
    xr = sp.Symbol(x.name, real=True)
    a, b = a.subs(x, xr), b.subs(x, xr)
    R = {"<": sp.StrictLessThan, ">": sp.StrictGreaterThan, "<=": sp.LessThan, ">=": sp.GreaterThan}[rel](a, b)
    try:
        sol = sp.solve_univariate_inequality(R, xr, relational=False)
    except Exception as e:
        raise NotSolved(f"No se pudo resolver la inecuación ({type(e).__name__})")
    # verificación: se evalúa la desigualdad ORIGINAL en puntos de prueba (entre extremos y fuera) y se compara con la pertenencia
    pts = set()
    ends = sorted({float(sp.N(v)) for v in sol.boundary if v.is_real and v.is_finite} | set(), key=float)
    cand = ends or [0.0]
    for i, e in enumerate(cand):
        pts.update({e - 1.37, e + 0.613})
        if i + 1 < len(cand): pts.add((e + cand[i + 1]) / 2)
    checked = 0
    ok = True
    for v in sorted(pts):
        q = sp.Rational(str(round(v, 6)))
        lv, rv = _num(a, {xr: q}), _num(b, {xr: q})
        if lv is None or rv is None or abs(lv.imag) > 1e-12 or abs(rv.imag) > 1e-12: continue
        truth = {"<": lv.real < rv.real, ">": lv.real > rv.real, "<=": lv.real <= rv.real, ">=": lv.real >= rv.real}[rel]
        if bool(sol.contains(q)) != truth: ok = False
        checked += 1
    _check(ok, "evaluación en puntos de prueba")
    txt = _set_text(sol)
    return _res(txt, "sympy_inecuacion_real",
                ("passed" if checked else "not_possible", f"desigualdad original evaluada en {checked} puntos de prueba" if checked else None),
                data={"variable": x.name, "set_latex": _latex(sol)}, latex=x.name + r" \in " + (_latex(sol) or ""),
                status="success_exact" if sol != sp.S.EmptySet else "no_solution")


def _set_text(s):
    sp = _sp()
    if s == sp.S.EmptySet: return "∅ (sin solución)"
    if s == sp.S.Reals: return "todos los reales"
    if isinstance(s, sp.Union): return " ∪ ".join(_set_text(a) for a in s.args)
    if isinstance(s, sp.Interval):
        l = "-∞" if s.start == -sp.oo else _txt(s.start)
        r = "∞" if s.end == sp.oo else _txt(s.end)
        return ("(" if s.left_open else "[") + l + ", " + r + (")" if s.right_open else "]")
    if isinstance(s, sp.FiniteSet): return "{" + ", ".join(_txt(a) for a in s.args) + "}"
    if isinstance(s, sp.Complement): return _set_text(s.args[0]) + " excepto " + _set_text(s.args[1])
    return _txt(s)


# ------------------------------------------------------------------ números complejos
def _cval(n):
    """Evaluador complejo PROPIO (cmath) sobre el AST: vía independiente de SymPy para verificar."""
    k = n[0]
    if k == "num": return complex(n[1])
    if k == "sym":
        if n[1] == "i": return 1j
        if n[1] == "pi": return complex(math.pi)
        if n[1] == "e": return complex(math.e)
        raise InvalidRequest(f"Variable '{n[1]}' sin valor en un número complejo")
    if k == "neg": return -_cval(n[1])
    if k == "bin":
        a, b = _cval(n[2]), _cval(n[3])
        return {"+": lambda: a + b, "-": lambda: a - b, "*": lambda: a * b, "/": lambda: a / b, "^": lambda: a ** b}[n[1]]()
    if k == "call":
        f = {"sin": cmath.sin, "cos": cmath.cos, "tan": cmath.tan, "exp": cmath.exp, "ln": cmath.log, "log": cmath.log,
             "sqrt": cmath.sqrt, "abs": lambda z: complex(abs(z)), "sinh": cmath.sinh, "cosh": cmath.cosh, "tanh": cmath.tanh,
             "asin": cmath.asin, "acos": cmath.acos, "atan": cmath.atan}.get(n[1])
        if f is None or len(n[2]) != 1: raise NotImplementedOperation(f"Función '{n[1]}' no soportada en complejos")
        return f(_cval(n[2][0]))
    raise ParseError("Nodo desconocido")


def op_complex(req, st):
    sp = _sp()
    ast = _ast(req["expression"])
    if free_symbols(ast) - {"i", "pi", "e"}:
        raise InvalidRequest("Números complejos: la expresión no debe tener variables (use i como unidad imaginaria)")
    z = symbolic.to_sympy(ast)
    re_, im_ = sp.simplify(sp.re(sp.expand_complex(z))), sp.simplify(sp.im(sp.expand_complex(z)))
    w = sp.simplify(re_ + sp.I * im_)
    mod = sp.simplify(sp.sqrt(re_ ** 2 + im_ ** 2))
    arg = sp.simplify(sp.atan2(im_, re_)) if (re_ != 0 or im_ != 0) else sp.Integer(0)
    try:
        ref = _cval(ast)
    except ZeroDivisionError:
        raise MathDomainError("División por cero")
    ok = _close(complex(sp.N(w, 30)), ref, 1e-9)
    _check(ok, "evaluación con cmath")
    deg = float(sp.N(arg * 180 / sp.pi, 20))
    data = {"real": _txt(re_), "imaginary": _txt(im_), "modulus": _txt(mod), "argument": _txt(arg),
            "argument_degrees": format(deg, ".10g"), "conjugate": _txt(sp.simplify(re_ - sp.I * im_)),
            "polar": f"{_txt(mod)} ∠ {format(deg, '.6g')}°",
            "polar_latex": _latex(mod) + r"\,e^{i" + _latex(arg) + "}"}
    approx = _fmt(complex(sp.N(w, 20)))
    return _res(_txt(w), "aritmetica_compleja_sympy", ("passed", "evaluación independiente con cmath"), data=data,
                approx=approx, latex=_latex(w) + r"\quad=\quad " + data["polar_latex"])


# ------------------------------------------------------------------ ecuaciones diferenciales ordinarias
_DER = re.compile(r"([A-Za-z_]\w*)('+)")


def op_ode(req, st):
    sp = _sp()
    names = req.get("variables") or []
    fname = names[0] if names else "y"
    xname = names[1] if len(names) > 1 else ("t" if re.search(r"\bt\b", req["expression"]) and not re.search(r"\bx\b", req["expression"]) else "x")
    x = sp.Symbol(xname)
    f = sp.Function(fname)

    def conv(text):
        mapping = {}

        def rep(m):
            if m.group(1) != fname: raise ParseError(f"Solo se admite la función incógnita '{fname}'")
            key = f"D{len(m.group(2))}{fname}"
            mapping[key] = len(m.group(2))
            return key
        t2 = _DER.sub(rep, text)
        e = _S(t2)
        sub = {sp.Symbol(k): sp.Derivative(f(x), (x, o)) for k, o in mapping.items()}
        sub[sp.Symbol(fname)] = f(x)
        return e.subs(sub)

    eqs = [s for s in re.split(r"[;\n]", req["expression"]) if s.strip()]
    if len(eqs) != 1: raise InvalidRequest("Escriba una ecuación diferencial (las condiciones iniciales van aparte)")
    if "=" in eqs[0]:
        l, r = eqs[0].split("=", 1)
        eq = sp.Eq(conv(l), conv(r))
    else:
        eq = sp.Eq(conv(eqs[0]), 0)
    ics = {}
    for c in (req.get("conditions") or []):
        m = re.match(r"^\s*" + re.escape(fname) + r"('*)\(([^)]+)\)\s*=\s*(.+)$", c)
        if not m: raise ParseError(f"Condición no reconocida: {c} (use p. ej. {fname}(0)=1, {fname}'(0)=0)")
        o = len(m.group(1))
        x0, v = _S(m.group(2)), _S(m.group(3))
        key = f(x0) if o == 0 else sp.Derivative(f(x), (x, o)).subs(x, x0)
        ics[key] = v
    try:
        sol = sp.dsolve(eq, f(x), ics=ics or None)
    except NotImplementedError:
        raise NotSolved("SymPy no tiene un método para esta ecuación (no implica que no tenga solución)")
    except ValueError as e:
        raise NotSolved(f"No se pudieron imponer las condiciones: {e}")
    sols = sol if isinstance(sol, list) else [sol]
    # verificación independiente: sustitución de la solución en la ecuación ORIGINAL (checkodesol) y de las condiciones
    ok = True
    for s in sols:
        good, _rest = sp.checkodesol(eq, s)
        if not good: ok = False
        for k, v in ics.items():
            if isinstance(k, sp.Subs):
                expr_d, pt = k.args[0], k.args[2][0]
                val = sp.diff(s.rhs, x, expr_d.derivative_count).subs(x, pt)
            else:
                val = s.rhs.subs(x, k.args[0])
            if sp.simplify(val - v) != 0: ok = False
    _check(ok, "sustitución en la ecuación")
    txt = "; ".join(f"{fname}({xname}) = {_txt(s.rhs)}" for s in sols)
    lat = r",\quad ".join(_latex(s) for s in sols)
    return _res(txt, "sympy_dsolve", ("passed", "sustitución de la solución en la ecuación original" + (" y en las condiciones iniciales" if ics else "")),
                data={"function": fname, "variable": xname, "general": not bool(ics),
                      "note": "C1, C2… son constantes arbitrarias" if not ics else ""}, latex=lat)


# ------------------------------------------------------------------ transformada de Laplace
def _laplace_num_ok(f, t, F, s, a):
    """∫₀^∞ f(t) e^{-st} dt con cuadratura de mpmath (independiente de SymPy) frente a F(s) en dos valores de s."""
    import mpmath
    sp = _sp()
    mpmath.mp.dps = 30
    heav = {"Heaviside": lambda z, h=0.5: 1 if z > 0 else (h if z == 0 else 0), "DiracDelta": lambda z: 0}
    fl = sp.lambdify(t, f, [heav, "mpmath"])
    Fl = sp.lambdify(s, F, [heav, "mpmath"])
    base = float(a) if a is not None and a not in (-sp.oo,) and getattr(a, "is_finite", True) else 0.0
    if f.has(sp.DiracDelta): return None
    good = 0
    for sv in (base + 1.5, base + 3.25):
        try:
            I = mpmath.quad(lambda tt: fl(tt) * mpmath.exp(-sv * tt), [0, 1, 10, mpmath.inf])
            ref = Fl(mpmath.mpf(sv))
            if abs(I - ref) > 1e-8 * max(1, abs(ref)): return False
            good += 1
        except Exception:
            continue
    return True if good else None


def op_laplace(req, st):
    sp = _sp()
    f = _S(req["expression"])
    t = sp.Symbol((req.get("variables") or ["t"])[0])
    s = sp.Symbol("s")
    f = f.subs(t, sp.Symbol(t.name, positive=True)); t = sp.Symbol(t.name, positive=True)
    F, a, cond = sp.laplace_transform(f, t, s)
    if F.has(sp.LaplaceTransform): raise NotSolved("SymPy no encontró la transformada")
    F = sp.simplify(F)
    ok = _laplace_num_ok(f, t, F, s, a)
    _check(ok, "integral numérica")
    conds = [f"Re(s) > {_txt(a)}"] if a not in (None, -sp.oo) else []
    return _res(_txt(F), "sympy_laplace_transform",
                ("passed" if ok else "not_possible", "∫₀^∞ f(t)e^(−st)dt por cuadratura numérica (mpmath) en dos valores de s" if ok else None),
                data={"region": conds[0] if conds else "todo s"}, latex=r"\mathcal{L}\{" + _latex(f) + r"\} = " + _latex(F),
                conditions=conds)


def op_inverse_laplace(req, st):
    sp = _sp()
    F = _S(req["expression"])
    s = sp.Symbol((req.get("variables") or ["s"])[0])
    F = F.subs(sp.Symbol(s.name), s)
    t = sp.Symbol("t", positive=True)
    f = sp.inverse_laplace_transform(F, s, t)
    if f.has(sp.InverseLaplaceTransform): raise NotSolved("SymPy no encontró la transformada inversa")
    f = sp.simplify(f.subs(sp.Heaviside(t), 1))
    # región de convergencia: a la derecha de los polos reales
    try:
        poles = [complex(sp.N(p)).real for p in sp.roots(sp.denom(sp.together(F)), s)]
        a = max(poles) if poles else 0
    except Exception:
        a = 0
    ok = _laplace_num_ok(f, t, F, s, a)
    _check(ok, "integral numérica")
    return _res(_txt(f), "sympy_inverse_laplace",
                ("passed" if ok else "not_possible", "transformada directa del resultado por cuadratura numérica (mpmath) comparada con F(s)" if ok else None),
                data={"note": "válida para t > 0"}, latex=r"\mathcal{L}^{-1}\{" + _latex(F) + r"\} = " + _latex(f))


# ------------------------------------------------------------------ estadística descriptiva
def _parse_data(text):
    vals = []
    for tok in re.split(r"[,;\s]+", text.strip()):
        if not tok: continue
        v = _ast(tok)
        from .arith import evaluate
        q = evaluate(v)
        vals.append(Fraction(q))
    if len(vals) < 1: raise InvalidRequest("Escriba los datos separados por comas")
    if len(vals) > 100000: raise InvalidRequest("Demasiados datos")
    return vals


def _ftxt(q):
    q = Fraction(q)
    return str(q.numerator) if q.denominator == 1 else f"{q.numerator}/{q.denominator}"


def op_stats(req, st):
    sp = _sp()
    xs = _parse_data(req["expression"])
    n = len(xs)
    s = sorted(xs)
    mean = sum(xs, Fraction(0)) / n
    med = s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2
    counts = {}
    for v in xs: counts[v] = counts.get(v, 0) + 1
    top = max(counts.values())
    modes = sorted(v for v, c in counts.items() if c == top) if top > 1 else []
    ss = sum((v - mean) ** 2 for v in xs)
    var_p = ss / n
    var_s = ss / (n - 1) if n > 1 else None
    sd_p = sp.sqrt(sp.Rational(var_p.numerator, var_p.denominator))
    sd_s = sp.sqrt(sp.Rational(var_s.numerator, var_s.denominator)) if var_s is not None else None

    def q_(p):   # cuartiles por interpolación lineal (método "inclusive", el de la mayoría de calculadoras)
        h = (n - 1) * Fraction(p)
        lo = int(h)
        return s[lo] + (h - lo) * (s[min(lo + 1, n - 1)] - s[lo])
    q1, q3 = q_(Fraction(1, 4)), q_(Fraction(3, 4))
    # verificación independiente con el módulo statistics de Python (coma flotante)
    fx = [float(v) for v in xs]
    ok = _close(float(mean), statistics.fmean(fx)) and _close(float(med), statistics.median(fx)) and \
        _close(float(var_p), statistics.pvariance(fx), 1e-8) and (var_s is None or _close(float(var_s), statistics.variance(fx), 1e-8))
    if n >= 2:
        qq = statistics.quantiles(fx, n=4, method="inclusive")
        ok = ok and _close(float(q1), qq[0]) and _close(float(q3), qq[2])
    _check(ok, "módulo statistics")
    data = {"n": n, "sum": _ftxt(sum(xs, Fraction(0))), "mean": _ftxt(mean), "median": _ftxt(med),
            "mode": [_ftxt(m) for m in modes], "min": _ftxt(s[0]), "max": _ftxt(s[-1]), "range": _ftxt(s[-1] - s[0]),
            "variance_population": _ftxt(var_p), "variance_sample": _ftxt(var_s) if var_s is not None else None,
            "std_population": _txt(sd_p), "std_sample": _txt(sd_s) if sd_s is not None else None,
            "q1": _ftxt(q1), "q3": _ftxt(q3), "iqr": _ftxt(q3 - q1),
            "approx": {"mean": format(float(mean), ".10g"), "std_population": format(float(sp.N(sd_p)), ".10g"),
                       "std_sample": format(float(sp.N(sd_s)), ".10g") if sd_s is not None else None}}
    txt = f"n = {n}; media = {data['mean']}; mediana = {data['median']}; desviación típica muestral = {data['std_sample']}"
    return _res(txt, "estadistica_descriptiva_exacta", ("passed", "comparado con el módulo statistics de Python"), data=data,
                approx=f"media ≈ {data['approx']['mean']}")


# ------------------------------------------------------------------ unidades y análisis dimensional
def _units():
    from sympy.physics import units as u
    k, M, c, m, mu, n, p = u.kilo, u.mega, u.centi, u.milli, u.micro, u.nano, u.pico
    return {
        "m": u.meter, "cm": c * u.meter, "mm": m * u.meter, "km": k * u.meter, "um": mu * u.meter, "nm": n * u.meter,
        "in": u.inch, "inch": u.inch, "ft": u.foot, "yd": u.yard, "mi": u.mile,
        "s": u.second, "ms": m * u.second, "us": mu * u.second, "min": u.minute, "h": u.hour, "day": u.day,
        "g": u.gram, "kg": u.kilogram, "mg": m * u.gram, "lb": u.pound, "t": u.tonne,
        "N": u.newton, "kN": k * u.newton, "J": u.joule, "kJ": k * u.joule, "cal": _sp().Rational(4184, 1000) * u.joule, "kcal": 4184 * u.joule,   # caloría termoquímica
        "W": u.watt, "kW": k * u.watt, "MW": M * u.watt, "hp": _sp().Rational(74569987158227022, 10 ** 14) * u.watt,
        "Wh": u.watt * u.hour, "kWh": k * u.watt * u.hour,
        "V": u.volt, "mV": m * u.volt, "kV": k * u.volt, "A": u.ampere, "mA": m * u.ampere,
        "ohm": u.ohm, "kohm": k * u.ohm, "Mohm": M * u.ohm, "F": u.farad, "uF": mu * u.farad,
        "nF": n * u.farad, "pF": p * u.farad, "H": u.henry, "mH": m * u.henry,
        "Hz": u.hertz, "kHz": k * u.hertz, "MHz": M * u.hertz, "C": u.coulomb, "S": u.siemens,
        "Pa": u.pascal, "kPa": k * u.pascal, "MPa": M * u.pascal, "bar": u.bar, "atm": u.atmosphere, "psi": u.psi,
        "L": u.liter, "mL": m * u.liter, "rad": u.radian, "deg": u.degree,
    }


def _parse_quantity(text):
    sp = _sp()
    U = _units()
    t = text.replace("Ω", "ohm").replace("µ", "u").replace("°", "deg")
    ast = _ast(t)
    syms = free_symbols(ast)
    unknown = [s for s in syms if s not in U]
    if unknown: raise InvalidRequest("Unidades no reconocidas: " + ", ".join(sorted(unknown)), {"known": sorted(U)})
    e = symbolic.to_sympy(ast)
    return e.subs({sp.Symbol(k): v for k, v in U.items() if k in syms}), t


def op_units(req, st):
    sp = _sp()
    from sympy.physics.units import convert_to
    from sympy.physics.units.systems.si import SI
    text = req["expression"]
    m = re.split(r"\s+(?:to|en|a|->|→)\s+", text, maxsplit=1)
    q, _ = _parse_quantity(m[0])
    try:
        factor, dim = SI._collect_factor_and_dimension(q)
    except ValueError as e:
        raise MathDomainError("Magnitudes dimensionalmente incompatibles: " + str(e).split("\n")[0])
    if len(m) == 1:
        deps = SI.get_dimension_system().get_dimensional_dependencies(dim)
        base = convert_to(q, [x for x in _units_base()])
        return _res(_txt(sp.nsimplify(base) if base.is_number else base), "analisis_dimensional_SI",
                    ("passed", "dimensiones homogéneas"), data={"dimension": {str(k): int(v) for k, v in deps.items()}},
                    latex=_latex(base))
    target, _ = _parse_quantity(m[1])
    tf, tdim = SI._collect_factor_and_dimension(target)
    dsys = SI.get_dimension_system()
    if dsys.get_dimensional_dependencies(dim) != dsys.get_dimensional_dependencies(tdim):
        raise MathDomainError(f"No se puede convertir: dimensiones distintas ({dim.name} → {tdim.name})")
    val = sp.nsimplify(sp.simplify(factor / tf))
    # verificación independiente: reconvertir con convert_to y comparar con el cociente de factores SI
    back = convert_to(q, target)
    ok = _close(complex(sp.N(back / target)), complex(sp.N(val)), 1e-12)
    _check(ok, "reconversión")
    unit_txt = m[1].strip()
    return _res(f"{_txt(val)} {unit_txt}", "conversion_unidades_SI", ("passed", "factores del SI y reconversión con convert_to"),
                approx=f"{format(float(sp.N(val, 20)), '.12g')} {unit_txt}", data={"value": _txt(val), "unit": unit_txt},
                latex=_latex(val) + r"\ \mathrm{" + unit_txt.replace("ohm", r"\Omega") + "}")


def _units_base():
    from sympy.physics import units as u
    return [u.meter, u.kilogram, u.second, u.ampere, u.kelvin, u.mole, u.candela]


# ------------------------------------------------------------------ biblioteca de fórmulas (ingeniería eléctrica y física)
FORMULAS = {
    "ohm": ("Ley de Ohm", "V = I*R", {"V": "tensión (V)", "I": "corriente (A)", "R": "resistencia (Ω)"}),
    "potencia_vi": ("Potencia eléctrica", "P = V*I", {"P": "potencia (W)", "V": "tensión (V)", "I": "corriente (A)"}),
    "potencia_ir": ("Potencia disipada (Joule)", "P = I^2*R", {"P": "potencia (W)", "I": "corriente (A)", "R": "resistencia (Ω)"}),
    "potencia_vr": ("Potencia con tensión y resistencia", "P = V^2/R", {"P": "potencia (W)", "V": "tensión (V)", "R": "resistencia (Ω)"}),
    "energia": ("Energía eléctrica", "E = P*t", {"E": "energía (J o Wh)", "P": "potencia (W)", "t": "tiempo (s o h)"}),
    "divisor_tension": ("Divisor de tensión", "Vout = Vin*R2/(R1+R2)", {"Vout": "salida (V)", "Vin": "entrada (V)", "R1": "Ω", "R2": "Ω"}),
    "paralelo_2": ("Dos resistencias en paralelo", "Req = R1*R2/(R1+R2)", {"Req": "Ω", "R1": "Ω", "R2": "Ω"}),
    "reactancia_l": ("Reactancia inductiva", "XL = 2*pi*f*L", {"XL": "Ω", "f": "frecuencia (Hz)", "L": "inductancia (H)"}),
    "reactancia_c": ("Reactancia capacitiva", "XC = 1/(2*pi*f*C)", {"XC": "Ω", "f": "frecuencia (Hz)", "C": "capacidad (F)"}),
    "impedancia_rlc": ("Impedancia RLC serie (módulo)", "Z = sqrt(R^2+(XL-XC)^2)", {"Z": "Ω", "R": "Ω", "XL": "Ω", "XC": "Ω"}),
    "resonancia": ("Frecuencia de resonancia LC", "f0 = 1/(2*pi*sqrt(L*C))", {"f0": "Hz", "L": "H", "C": "F"}),
    "tau_rc": ("Constante de tiempo RC", "tau = R*C", {"tau": "s", "R": "Ω", "C": "F"}),
    "trifasica_p": ("Potencia activa trifásica", "P = sqrt(3)*VL*IL*fp", {"P": "W", "VL": "tensión de línea (V)", "IL": "corriente de línea (A)", "fp": "factor de potencia"}),
    "trifasica_s": ("Potencia aparente trifásica", "S = sqrt(3)*VL*IL", {"S": "VA", "VL": "V", "IL": "A"}),
    "triangulo_potencias": ("Triángulo de potencias", "S = sqrt(P^2+Q^2)", {"S": "VA", "P": "W", "Q": "var"}),
    "transformador": ("Transformador ideal", "Vp/Vs = Np/Ns", {"Vp": "primario (V)", "Vs": "secundario (V)", "Np": "espiras primario", "Ns": "espiras secundario"}),
    "caida_tension": ("Caída de tensión en un conductor (monofásico)", "dV = 2*L*I*rho/A", {"dV": "V", "L": "longitud (m)", "I": "A", "rho": "resistividad (Ω·mm²/m)", "A": "sección (mm²)"}),
}


def op_formula(req, st):
    sp = _sp()
    params = req.get("params") or {}
    fid = params.get("id")
    if fid not in FORMULAS:
        raise InvalidRequest("Fórmula desconocida", {"available": {k: v[0] for k, v in FORMULAS.items()}})
    name, eq_txt, desc = FORMULAS[fid]
    l, r = eq_txt.split("=")
    L, R = _S(l), _S(r)
    known = {k: _S(str(v)) for k, v in (params.get("known") or {}).items() if str(v).strip() != ""}
    unknown = params.get("unknown")
    if unknown not in desc: raise InvalidRequest(f"Incógnita no válida; elija una de: {', '.join(desc)}")
    missing = [v for v in desc if v != unknown and v not in known]
    if missing: raise InvalidRequest("Faltan datos: " + ", ".join(missing))
    u = sp.Symbol(unknown, positive=True)
    eq = sp.Eq(L, R).subs({sp.Symbol(unknown): u}).subs({sp.Symbol(k): v for k, v in known.items()})
    sols = sp.solve(eq, u)
    sols = [sp.nsimplify(sp.simplify(s)) for s in sols if s.is_real is not False]
    if not sols: raise NotSolved("No hay solución positiva con esos datos")
    ok = all(_close(complex(sp.N(eq.lhs.subs(u, s), 30)), complex(sp.N(eq.rhs.subs(u, s), 30)), 1e-12) for s in sols)
    _check(ok, "sustitución")
    txt = ", ".join(f"{unknown} = {_txt(s)}" for s in sols)
    approx = ", ".join(f"{unknown} ≈ {format(float(sp.N(s, 20)), '.10g')}" for s in sols)
    return _res(txt, "biblioteca_de_formulas", ("passed", "sustitución del resultado en la fórmula"), approx=approx,
                data={"formula": eq_txt, "name": name, "unit": desc[unknown]},
                latex=r",\ ".join(f"{unknown} = " + _latex(s) for s in sols))


def formulas_catalog():
    return [{"id": k, "name": v[0], "equation": v[1], "variables": v[2]} for k, v in FORMULAS.items()]


def run(req, st):
    op = req["operation"]
    _sp()
    if op == "eigen":
        si = req.get("structured_input") or {}
        a = si.get("a", req.get("expression"))
        if isinstance(a, str):
            from math_universe_linalg import api as LA  # noqa: F401
            a = [[c.strip() for c in row.split(",")] for row in re.findall(r"\[([^\[\]]+)\]", a)]
        return op_eigen(req, st, a)
    fn = {"partial": op_partial, "gradient": op_gradient, "hessian": op_hessian, "jacobian": op_jacobian,
          "series": op_series, "inequality": op_inequality, "complex": op_complex, "ode": op_ode, "laplace": op_laplace,
          "inverse_laplace": op_inverse_laplace, "stats": op_stats, "units": op_units, "formula": op_formula}[op]
    if op != "formula" and not req.get("expression"): raise InvalidRequest("Falta 'expression'")
    return fn(req, st)
