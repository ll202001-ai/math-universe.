"""Presentación matemática (motor 0.6.0): LaTeX de la entrada y del resultado, sin recalcular nada.

Se construye la expresión SymPy con evaluate(False) para que lo que se dibuja sea EXACTAMENTE lo que produjo el motor
(sin simplificaciones automáticas como sqrt(x)^2 → x, que cambiarían el dominio). Si algo no se puede convertir, se
devuelve None y la interfaz muestra el texto.
"""
import re

from . import symbolic
from .ast_tools import normalize
from .parser import parse

_MAX = 4000


def _expr_latex(text):
    sp = symbolic.sp
    if sp is None: return None
    t = text.strip()
    if not t: return None
    plus_c = False
    if t.endswith("+ C"):
        t, plus_c = t[:-3].strip(), True
    ast = parse(t)
    with sp.evaluate(False):
        e = _flat(symbolic.to_sympy(ast))
    out = sp.latex(e, order="none", ln_notation=True)
    return out + (" + C" if plus_c else "")


def _flat(e):
    """Aplana sumas y productos anidados (el árbol del parser es binario) SIN evaluar: (a + b) + c → a + b + c."""
    sp = symbolic.sp
    if not getattr(e, "args", None): return e
    args = [_flat(a) for a in e.args]
    if isinstance(e, (sp.Add, sp.Mul)):
        flat = []
        for a in args:
            flat.extend(a.args if type(a) is type(e) else [a])
        return type(e)(*flat, evaluate=False)
    try:
        return e.func(*args, evaluate=False)
    except TypeError:
        return e.func(*args)


def _matrix_latex(text):
    rows = re.findall(r"\[([^\[\]]*)\]", text)
    if not rows: return None
    body = r" \\ ".join(" & ".join(_expr_latex(c) or c for c in r.split(",")) for r in rows)
    return r"\begin{pmatrix}" + body + r"\end{pmatrix}"


def latex_of(text):
    """LaTeX de un texto del motor: expresión, ecuación, lista de ecuaciones 'x = 2, x = 3', matriz [[..]] o sistema 'a; b'."""
    try:
        if text is None or len(text) > _MAX: return None
        t = text.strip()
        if t in ("Verdadero", "Falso"): return r"\text{" + t + "}"
        if t.startswith("[["): return _matrix_latex(t)
        if ";" in t or "\n" in t:
            parts = [p for p in re.split(r"[;\n]", t) if p.strip()]
            return r"\begin{cases}" + r" \\ ".join(latex_of(p) or p for p in parts) + r"\end{cases}"
        if "=" in t:
            items = [p.strip() for p in t.split(",")] if all("=" in p for p in t.split(",")) else [t]
            outs = []
            for it in items:
                sides = [s.strip() for s in it.split("=")]
                ls = [_expr_latex(s) for s in sides]
                if any(x is None for x in ls): return None
                outs.append(" = ".join(ls))
            return r",\quad ".join(outs)
        return _expr_latex(t)
    except Exception:
        return None
