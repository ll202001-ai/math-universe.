"""Procedimiento paso a paso (motor 0.6.0).

Los pasos se GENERAN con las mismas reglas matemáticas que se describen (no son texto decorativo) y cada secuencia se
CONTRASTA con el resultado del motor: si el último paso no coincide exactamente con lo que el motor calculó, no se
muestran pasos. Cubiertos: ecuaciones de primer y segundo grado en una variable, derivadas (reglas de derivación) y
eliminación de Gauss-Jordan (sistemas e inversas).
"""
from fractions import Fraction

from . import symbolic

MAX_STEPS = 40


def _sp():
    return symbolic.sp


def _L(e):
    return _sp().latex(e, ln_notation=True)


def _step(text, latex=None):
    return {"text": text, "latex": latex}


# ------------------------------------------------------------------ ecuaciones de grado 1 y 2
def solve_steps(expression, variables, engine_solutions):
    sp = _sp()
    if sp is None or ";" in expression or "\n" in expression or expression.count("=") != 1: return None
    l, r = expression.split("=")
    L, R = symbolic.to_sympy(_ast(l)), symbolic.to_sympy(_ast(r))
    syms = sorted((L - R).free_symbols, key=lambda s: s.name)
    if variables: x = sp.Symbol(variables[0])
    elif len(syms) == 1: x = syms[0]
    else: return None
    e = sp.expand(L - R)
    if not e.is_polynomial(x) or (e.free_symbols - {x}): return None
    p = sp.Poly(e, x)
    d = p.degree()
    steps = [_step("Ecuación original", _L(sp.Eq(L, R, evaluate=False)))]
    if d == 1:
        a, b = p.all_coeffs()
        steps.append(_step("Se pasan todos los términos a un lado y se agrupan", _L(sp.Eq(a * x + b, 0, evaluate=False))))
        steps.append(_step("Se despeja el término con " + x.name, _L(sp.Eq(a * x, -b, evaluate=False))))
        if a != 1: steps.append(_step(f"Se divide entre {sp.sstr(a)}", _L(sp.Eq(x, sp.Mul(-b, sp.Pow(a, -1, evaluate=False), evaluate=False), evaluate=False))))
        sol = [sp.simplify(-b / a)]
    elif d == 2:
        a, b, c = p.all_coeffs()
        steps.append(_step(f"Forma general a·{x.name}² + b·{x.name} + c = 0 con a = {sp.sstr(a)}, b = {sp.sstr(b)}, c = {sp.sstr(c)}",
                           _L(sp.Eq(a * x ** 2 + b * x + c, 0, evaluate=False))))
        D = b ** 2 - 4 * a * c
        P = lambda v: (r"\left(" + _L(v) + r"\right)") if v < 0 else _L(v)
        steps.append(_step("Discriminante Δ = b² − 4ac", r"\Delta = " + P(b) + r"^{2} - 4\cdot " + P(a) + r"\cdot " + P(c) + " = " + _L(D)))
        if D < 0:
            steps.append(_step("Δ < 0: no hay soluciones reales"))
            sol = []
        else:
            steps.append(_step("Fórmula cuadrática", x.name + r" = \frac{-b \pm \sqrt{\Delta}}{2a} = \frac{" + _L(-b) + r" \pm \sqrt{" + _L(D) + r"}}{" + _L(2 * a) + "}"))
            r1, r2 = sp.simplify((-b - sp.sqrt(D)) / (2 * a)), sp.simplify((-b + sp.sqrt(D)) / (2 * a))
            sol = sorted({r1, r2}, key=lambda v: float(sp.N(v)))
            if D == 0: steps.append(_step("Δ = 0: una raíz doble"))
            fac = sp.factor(a * x ** 2 + b * x + c)
            if fac.is_Mul or fac.is_Pow: steps.append(_step("Comprobación por factorización", _L(sp.Eq(fac, 0, evaluate=False))))
    else:
        return None
    steps.append(_step("Solución", r",\quad ".join(x.name + " = " + _L(s) for s in sol) if sol else r"\varnothing"))
    # contraste con el motor
    try:
        eng = sorted({sp.simplify(symbolic.to_sympy(_ast(v))) for v in engine_solutions}, key=lambda v: float(sp.N(v)))
    except Exception:
        return None
    if len(eng) != len(sol) or any(sp.simplify(a - b) != 0 for a, b in zip(eng, sol)): return None
    return steps


def _ast(t):
    from .ast_tools import normalize
    from .parser import parse
    return normalize(parse(t))


# ------------------------------------------------------------------ derivadas
def derivative_steps(expression, variables, engine_result):
    sp = _sp()
    if sp is None: return None
    with sp.evaluate(False):
        f = symbolic.to_sympy(_ast(expression))
    f = f.doit() if hasattr(f, "doit") else f
    syms = sorted(f.free_symbols, key=lambda s: s.name)
    x = sp.Symbol(variables[0]) if variables else (syms[0] if len(syms) == 1 else None)
    if x is None: return None
    steps = [_step("Función a derivar", r"\frac{d}{d" + x.name + r"}\left[" + _L(f) + r"\right]")]
    _rules(f, x, steps, 0)
    d = sp.diff(f, x)
    steps.append(_step("Resultado (simplificado)", r"\frac{d}{d" + x.name + "}" + r"\left[" + _L(f) + r"\right] = " + _L(sp.simplify(d))))
    try:
        if sp.simplify(d - symbolic.to_sympy(_ast(engine_result))) != 0: return None
    except Exception:
        return None
    return steps[:MAX_STEPS]


def _rules(f, x, steps, depth):
    sp = _sp()
    if len(steps) >= MAX_STEPS or depth > 6 or not f.has(x): return
    D = lambda e: r"\frac{d}{d" + x.name + r"}\left[" + _L(e) + r"\right]"
    if f.is_Add:
        steps.append(_step("Regla de la suma: se deriva término a término", D(f) + " = " + " + ".join(D(t) for t in f.args)))
        for t in f.args: _rules(t, x, steps, depth + 1)
        return
    if f.is_Mul:
        const = [a for a in f.args if not a.has(x)]
        var = [a for a in f.args if a.has(x)]
        if const:
            c = sp.Mul(*const); g = sp.Mul(*var)
            steps.append(_step("Factor constante: sale de la derivada", D(f) + " = " + _L(c) + r"\cdot " + D(g)))
            _rules(g, x, steps, depth + 1); return
        num = [a for a in var if not (a.is_Pow and a.exp.is_negative)]
        den = [sp.Pow(a.base, -a.exp) for a in var if a.is_Pow and a.exp.is_negative]
        if den and num:
            u, v = sp.Mul(*num), sp.Mul(*den)
            steps.append(_step("Regla del cociente: (u/v)' = (u'·v − u·v')/v²",
                               "u = " + _L(u) + r",\quad v = " + _L(v) + r",\quad u' = " + _L(sp.diff(u, x)) + r",\quad v' = " + _L(sp.diff(v, x))))
            _rules(u, x, steps, depth + 1); _rules(v, x, steps, depth + 1); return
        u, v = var[0], sp.Mul(*var[1:])
        steps.append(_step("Regla del producto: (u·v)' = u'·v + u·v'",
                           "u = " + _L(u) + r",\quad v = " + _L(v) + r",\quad u' = " + _L(sp.diff(u, x)) + r",\quad v' = " + _L(sp.diff(v, x))))
        _rules(u, x, steps, depth + 1); _rules(v, x, steps, depth + 1); return
    if f.is_Pow:
        b, n = f.args
        if not n.has(x):
            if b == x:
                steps.append(_step("Regla de la potencia: (xⁿ)' = n·xⁿ⁻¹", D(f) + " = " + _L(n) + r"\cdot " + _L(x ** (n - 1))))
            else:
                steps.append(_step("Regla de la cadena con la potencia: (uⁿ)' = n·uⁿ⁻¹·u'",
                                   "u = " + _L(b) + r",\quad " + D(f) + " = " + _L(n) + r"\cdot\left(" + _L(b) + r"\right)^{" + _L(n - 1) + r"}\cdot " + D(b)))
                _rules(b, x, steps, depth + 1)
            return
        if not b.has(x):
            steps.append(_step("Exponencial de base constante: (aᵘ)' = aᵘ·ln(a)·u'", D(f) + " = " + _L(f) + r"\ln\left(" + _L(b) + r"\right)\cdot " + D(n)))
            _rules(n, x, steps, depth + 1); return
        steps.append(_step("Derivación logarítmica: (uᵛ)' = uᵛ·(v'·ln u + v·u'/u)"))
        return
    if isinstance(f, sp.Function) and len(f.args) == 1:
        u = f.args[0]
        known = {sp.sin: r"\cos", sp.cos: r"-\sin", sp.exp: r"\exp", sp.log: "1/u", sp.tan: r"\sec^2"}
        name = type(f).__name__
        rule = {"sin": "(sin u)' = cos u · u'", "cos": "(cos u)' = −sin u · u'", "exp": "(eᵘ)' = eᵘ · u'",
                "log": "(ln u)' = u'/u", "tan": "(tan u)' = sec²u · u'", "asin": "(asin u)' = u'/√(1−u²)",
                "acos": "(acos u)' = −u'/√(1−u²)", "atan": "(atan u)' = u'/(1+u²)", "sinh": "(sinh u)' = cosh u · u'",
                "cosh": "(cosh u)' = sinh u · u'", "Abs": "(|u|)' = u·u'/|u| (u ≠ 0)"}.get(name)
        if rule:
            if u == x:
                steps.append(_step("Derivada de " + name + ": " + rule.replace("· u'", "").replace("u'", "1").replace("u", "x"),
                                   D(f) + " = " + _L(sp.diff(f, x))))
            else:
                steps.append(_step("Regla de la cadena: " + rule, "u = " + _L(u) + r",\quad " + D(f) + " = " + _L(sp.diff(f, x))))
                _rules(u, x, steps, depth + 1)
        return
    if f == x:
        return


# ------------------------------------------------------------------ Gauss-Jordan
def _fs(q):
    return str(q.numerator) if q.denominator == 1 else f"{q.numerator}/{q.denominator}"


def _mlatex(M, aug=None):
    cols = len(M[0])
    spec = "c" * cols if aug is None else "c" * aug + "|" + "c" * (cols - aug)
    rows = r" \\ ".join(" & ".join(_lq(v) for v in r) for r in M)
    return r"\left(\begin{array}{" + spec + "}" + rows + r"\end{array}\right)"


def _lq(q):
    if q.denominator == 1: return str(q.numerator)
    return ("-" if q < 0 else "") + r"\frac{" + str(abs(q.numerator)) + "}{" + str(q.denominator) + "}"


def gauss_steps(A, B=None):
    """Eliminación de Gauss-Jordan con registro de cada operación elemental. A, B: listas de Fraction."""
    M = [list(r) + (list(B[i]) if B is not None else []) for i, r in enumerate(A)]
    n, m = len(M), len(A[0])
    aug = m if B is not None else None
    steps = [_step("Matriz inicial" + (" ampliada [A | b]" if B is not None and len(B[0]) == 1 else " [A | I]" if B is not None else ""), _mlatex(M, aug))]
    row = 0
    for col in range(m):
        piv = next((r for r in range(row, n) if M[r][col] != 0), None)
        if piv is None: continue
        if piv != row:
            M[row], M[piv] = M[piv], M[row]
            steps.append(_step(f"Intercambiar F{row + 1} ↔ F{piv + 1}", _mlatex(M, aug)))
        p = M[row][col]
        if p != 1:
            M[row] = [v / p for v in M[row]]
            steps.append(_step(f"F{row + 1} → F{row + 1} ÷ ({_fs(p)})", _mlatex(M, aug)))
        ops = []
        for r in range(n):
            if r != row and M[r][col] != 0:
                k = M[r][col]
                M[r] = [a - k * b for a, b in zip(M[r], M[row])]
                ops.append(f"F{r + 1} → F{r + 1} − ({_fs(k)})·F{row + 1}")
        if ops: steps.append(_step("; ".join(ops), _mlatex(M, aug)))
        row += 1
        if row == n or len(steps) > MAX_STEPS: break
    steps.append(_step("Forma escalonada reducida", _mlatex(M, aug)))
    return steps, M
