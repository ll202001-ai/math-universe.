"""Muestreo de gráficas (motor 0.6.0). Toda la evaluación la hace el motor con el AST seguro; la interfaz solo dibuja.

plot   : y = f(x) (varias funciones separadas por ';'), en [xmin, xmax]. Devuelve segmentos continuos: los puntos no
         definidos y los saltos (asíntotas verticales) cortan la curva en vez de unirla con una línea falsa.
         También marca ceros (cambios de signo refinados por bisección) y extremos locales aproximados.
plot3d : z = f(x, y) en una rejilla [xmin, xmax] × [ymin, ymax].
param  : curva paramétrica x(t); y(t) en [tmin, tmax].
polar  : r = f(θ) en [θmin, θmax] (variable t o theta).
"""
import math
import re

from .ast_tools import eval_float, free_symbols, normalize
from .errors import InvalidRequest, MathDomainError, NotImplementedOperation
from .parser import parse

MAX_POINTS = 4000
MAX_GRID = 80


def _f(ast, var):
    def g(v):
        try:
            y = eval_float(ast, {var: v})
            if isinstance(y, complex) or y is None or math.isnan(y) or math.isinf(y): return None
            return float(y)
        except (MathDomainError, ValueError, ZeroDivisionError, OverflowError, NotImplementedOperation):
            return None
    return g


def _bounds(req, a="xmin", b="xmax", da=-10.0, db=10.0):
    p = req.get("params") or {}
    lo = float(p.get(a, da)); hi = float(p.get(b, db))
    if not (math.isfinite(lo) and math.isfinite(hi)) or hi <= lo:
        raise InvalidRequest("Intervalo de dibujo no válido")
    return lo, hi


def _var_of(ast, allowed):
    fs = free_symbols(ast) - {"pi", "e"}
    if len(fs) > 1: raise InvalidRequest("Use una sola variable (" + ", ".join(sorted(fs)) + ")")
    v = next(iter(fs)) if fs else allowed
    return v


def _sample(g, lo, hi, n):
    xs = [lo + (hi - lo) * i / (n - 1) for i in range(n)]
    ys = [g(x) for x in xs]
    finite = sorted(abs(y) for y in ys if y is not None)
    scale = finite[int(len(finite) * 0.9)] if finite else 1.0
    jump = max(1.0, scale) * 50
    segs, cur = [], []
    for i, (x, y) in enumerate(zip(xs, ys)):
        if y is None:
            if len(cur) > 1: segs.append(cur)
            cur = []
            continue
        if cur:
            py = cur[-1][1]
            # salto grande con cambio de signo o crecimiento explosivo = asíntota: no unir
            if abs(y - py) > jump and (py * y < 0 or abs(y) > jump or abs(py) > jump):
                if len(cur) > 1: segs.append(cur)
                cur = []
        cur.append([round(x, 12), y])
    if len(cur) > 1: segs.append(cur)
    return xs, ys, segs


def _roots(g, xs, ys):
    out = []
    for i in range(len(xs) - 1):
        a, b, fa, fb = xs[i], xs[i + 1], ys[i], ys[i + 1]
        if fa is None or fb is None: continue
        if fa == 0: out.append(a); continue
        if fa * fb < 0 and abs(fa - fb) < 1e6:
            for _ in range(60):
                m = (a + b) / 2; fm = g(m)
                if fm is None: break
                if fa * fm <= 0: b, fb = m, fm
                else: a, fa = m, fm
            r = (a + b) / 2
            fr = g(r)
            if fr is not None and abs(fr) < 1e-6: out.append(r)
    return [round(r, 10) for r in out][:50]


def _extrema(xs, ys):
    out = []
    for i in range(1, len(xs) - 1):
        a, b, c = ys[i - 1], ys[i], ys[i + 1]
        if None in (a, b, c): continue
        if b > a and b > c: out.append({"x": xs[i], "y": b, "kind": "max"})
        elif b < a and b < c: out.append({"x": xs[i], "y": b, "kind": "min"})
    return out[:50]


def op_plot(req, st):
    lo, hi = _bounds(req)
    n = min(int((req.get("params") or {}).get("samples", 600)), MAX_POINTS)
    funcs = [f.strip() for f in re.split(r"[;\n]", req["expression"]) if f.strip()]
    if not funcs or len(funcs) > 8: raise InvalidRequest("Entre 1 y 8 funciones separadas por ';'")
    series = []
    for text in funcs:
        if "=" in text:
            l, r = text.split("=", 1)
            if l.strip() in ("y", "f(x)"): text = r
        ast = normalize(parse(text))
        v = _var_of(ast, "x")
        g = _f(ast, v)
        xs, ys, segs = _sample(g, lo, hi, n)
        series.append({"expression": text.strip(), "variable": v, "segments": segs, "roots": _roots(g, xs, ys),
                       "extrema": _extrema(xs, ys)})
    allys = sorted(p[1] for s in series for seg in s["segments"] for p in seg)
    if allys:
        k = len(allys)
        ylo, yhi = allys[int(k * 0.02)], allys[min(k - 1, int(k * 0.98))]
        pad = (yhi - ylo) * 0.1 or 1.0
        yr = [ylo - pad, yhi + pad]
    else:
        yr = [-10, 10]
    return {"status": "success_exact", "exact_result": None, "method": "muestreo_del_motor",
            "verification": {"status": "not_performed", "method": None},
            "data": {"kind": "plot", "x_range": [lo, hi], "y_range": yr, "series": series},
            "warnings": ["Los ceros y extremos marcados son aproximaciones numéricas del muestreo"]}


def op_plot3d(req, st):
    lo, hi = _bounds(req)
    ylo, yhi = _bounds(req, "ymin", "ymax")
    n = min(int((req.get("params") or {}).get("grid", 40)), MAX_GRID)
    ast = normalize(parse(req["expression"].split("=", 1)[-1] if req["expression"].strip().startswith("z") else req["expression"]))
    fs = free_symbols(ast) - {"pi", "e"}
    if not fs <= {"x", "y"}: raise InvalidRequest("Superficies: use las variables x e y")
    zs = []
    for i in range(n):
        y = ylo + (yhi - ylo) * i / (n - 1)
        row = []
        for j in range(n):
            x = lo + (hi - lo) * j / (n - 1)
            try:
                z = eval_float(ast, {"x": x, "y": y})
                row.append(float(z) if z is not None and math.isfinite(z) else None)
            except Exception:
                row.append(None)
        zs.append(row)
    flat = sorted(z for r in zs for z in r if z is not None)
    zr = [flat[int(len(flat) * 0.02)], flat[min(len(flat) - 1, int(len(flat) * 0.98))]] if flat else [-1, 1]
    return {"status": "success_exact", "exact_result": None, "method": "muestreo_del_motor",
            "verification": {"status": "not_performed", "method": None},
            "data": {"kind": "plot3d", "x_range": [lo, hi], "y_range": [ylo, yhi], "z_range": zr, "grid": zs}}


def op_parametric(req, st, polar=False):
    lo, hi = _bounds(req, "tmin", "tmax", 0.0, 2 * math.pi)
    n = min(int((req.get("params") or {}).get("samples", 800)), MAX_POINTS)
    parts = [p.strip() for p in re.split(r"[;\n]", req["expression"]) if p.strip()]
    if polar:
        if len(parts) != 1: raise InvalidRequest("Curva polar: una expresión r(t)")
        r_ast = normalize(parse(parts[0].replace("theta", "t").replace("θ", "t")))
        rg = _f(r_ast, "t")
        fx = lambda t: (lambda r: None if r is None else r * math.cos(t))(rg(t))
        fy = lambda t: (lambda r: None if r is None else r * math.sin(t))(rg(t))
    else:
        if len(parts) != 2: raise InvalidRequest("Curva paramétrica: x(t); y(t)")
        fx, fy = (_f(normalize(parse(p)), "t") for p in parts)
    segs, cur = [], []
    for i in range(n):
        t = lo + (hi - lo) * i / (n - 1)
        x, y = fx(t), fy(t)
        if x is None or y is None:
            if len(cur) > 1: segs.append(cur)
            cur = []
            continue
        cur.append([x, y])
    if len(cur) > 1: segs.append(cur)
    pts = [p for s in segs for p in s]
    if not pts: raise MathDomainError("La curva no está definida en el intervalo")
    xr = [min(p[0] for p in pts), max(p[0] for p in pts)]
    yr = [min(p[1] for p in pts), max(p[1] for p in pts)]
    return {"status": "success_exact", "exact_result": None, "method": "muestreo_del_motor",
            "verification": {"status": "not_performed", "method": None},
            "data": {"kind": "polar" if polar else "parametric", "x_range": xr, "y_range": yr,
                     "series": [{"expression": req["expression"], "segments": segs, "roots": [], "extrema": []}]}}
