"""Interpretación de instrucciones en español (motor 0.6.0). Basada en reglas, sin IA: NO calcula nada.

Convierte frases como «deriva x al cubo por seno de x» o «límite de sin(x)/x cuando x tiende a 0» en una solicitud
del contrato (operation, expression, variables, point…) más un texto con la interpretación. La interfaz SIEMPRE muestra
la interpretación y pide confirmación antes de calcular. Si la frase no se entiende o es ambigua, se dice.
"""
import re

from .ast_tools import normalize
from .errors import ParseError
from .parser import parse

# palabras → sintaxis (orden importa: frases largas primero)
_WORDS = [
    (r"\bal cuadrado\b", "^2"), (r"\bal cubo\b", "^3"), (r"\belevad[oa] a(?:l)?\b", "^"), (r"\ba la\b", "^"),
    (r"\bra[ií]z cuadrada de\b", "sqrt "), (r"\bra[ií]z de\b", "sqrt "),
    (r"\bseno hiperb[oó]lico de\b", "sinh "), (r"\bcoseno hiperb[oó]lico de\b", "cosh "),
    (r"\barcoseno de\b", "asin "), (r"\barcocoseno de\b", "acos "), (r"\barcotangente de\b", "atan "),
    (r"\bseno de\b", "sin "), (r"\bcoseno de\b", "cos "), (r"\btangente de\b", "tan "),
    (r"\blogaritmo natural de\b", "ln "), (r"\blogaritmo de\b", "ln "), (r"\bexponencial de\b", "exp "),
    (r"\bvalor absoluto de\b", "abs "),
    (r"\bm[aá]s\b", "+"), (r"\bmenos\b", "-"), (r"\bpor\b", "*"), (r"\bentre\b", "/"), (r"\bdividido (?:entre|por)\b", "/"),
    (r"\bigual a\b", "="), (r"\bes igual a\b", "="),
    (r"\bpi\b", "pi"), (r"\bcero\b", "0"), (r"\buno\b", "1"), (r"\bdos\b", "2"), (r"\btres\b", "3"), (r"\bcuatro\b", "4"),
    (r"\bcinco\b", "5"), (r"\bseis\b", "6"), (r"\bsiete\b", "7"), (r"\bocho\b", "8"), (r"\bnueve\b", "9"), (r"\bdiez\b", "10"),
    (r"\binfinito\b", "oo"),
]

_OPS = [
    ("differentiate", r"^(?:deriva|derivar|derivada de|calcula la derivada de|halla la derivada de)\s+(.+)$", "Derivar"),
    ("integrate", r"^(?:integra|integrar|integral de|calcula la integral de|primitiva de)\s+(.+)$", "Integrar"),
    ("factor", r"^(?:factoriza|factorizar|factorizaci[oó]n de)\s+(.+)$", "Factorizar"),
    ("simplify", r"^(?:simplifica|simplificar)\s+(.+)$", "Simplificar"),
    ("expand", r"^(?:expande|expandir|desarrolla)\s+(.+)$", "Expandir"),
    ("solve", r"^(?:resuelve|resolver|soluciona|halla x en|encuentra x en)\s+(?:la ecuaci[oó]n\s+|el sistema\s+)?(.+)$", "Resolver"),
    ("evaluate", r"^(?:calcula|cu[aá]nto es|eval[uú]a)\s+(.+)$", "Calcular"),
    ("eigen", r"^(?:autovalores|valores propios|eigenvalores)\s+de\s+(.+)$", "Autovalores"),
    ("matrix_det", r"^(?:determinante|calcula el determinante)\s+de\s+(.+)$", "Determinante"),
    ("laplace", r"^(?:transformada de laplace de|laplace de)\s+(.+)$", "Transformada de Laplace"),
    ("series", r"^(?:serie de taylor de|taylor de|desarrollo en serie de)\s+(.+)$", "Serie de Taylor"),
    ("gradient", r"^(?:gradiente de)\s+(.+)$", "Gradiente"),
    ("units", r"^(?:convierte|convertir|pasa)\s+(.+)$", "Convertir unidades"),
]


def _to_math(text):
    t = " " + text.strip().rstrip(".?¿!¡") + " "
    for pat, rep in _WORDS:
        t = re.sub(pat, rep, t, flags=re.IGNORECASE)
    # «sin x» → «sin(x)» cuando la función va seguida de un solo término
    t = re.sub(r"\b(sin|cos|tan|asin|acos|atan|sinh|cosh|ln|exp|sqrt|abs)\s+([A-Za-z0-9_.^]+)", r"\1(\2)", t)
    t = re.sub(r"\s*\^\s*", "^", t)
    return re.sub(r"\s+", " ", t).strip()


def interpret(text):
    raw = text.strip()
    low = raw.lower()
    out = {"understood": False, "operation": None, "expression": None, "variables": [], "summary": None, "alternatives": []}
    # despeje: «despeja R en V = I*R»
    m = re.match(r"^(?:despeja|despejar|aísla|aisla)\s+([A-Za-z_]\w*)\s+(?:en|de)\s+(.+)$", raw, re.IGNORECASE)
    if m:
        expr = _to_math(m.group(2))
        return _ok(out, "solve", expr, [m.group(1)], f"Despejar {m.group(1)} en {expr}")
    # límite: «límite de f cuando x tiende a a»
    m = re.match(r"^(?:el\s+)?l[ií]mite de\s+(.+?)\s+cuando\s+([A-Za-z_]\w*)\s+tiende a\s+(.+)$", low)
    if m:
        expr = _to_math(raw[low.index(m.group(1)):low.index(m.group(1)) + len(m.group(1))])
        point = _to_math(m.group(3)).replace(" ", "")
        direction = None
        if point.endswith("por la derecha") or "+" == point[-1:] and point not in ("+oo",):
            direction = "+"
        r = _ok(out, "limit", expr, [m.group(2)], f"Límite de {expr} cuando {m.group(2)} → {point}")
        r["point"] = point.replace("porladerecha", "").replace("porlaizquierda", "")
        if direction: r["direction"] = direction
        return r
    for op, pat, label in _OPS:
        m = re.match(pat, low)
        if m:
            start = low.index(m.group(1))
            body = raw[start:start + len(m.group(1))]
            if op == "units":
                return _ok(out, op, body.replace(" a ", " to ").replace(" en ", " to "), [], f"{label}: {body}")
            var = []
            mv = re.search(r"\s+(?:respecto (?:a|de)|con respecto a|en funci[oó]n de)\s+([A-Za-z_]\w*)\s*$", body, re.IGNORECASE)
            if mv:
                var = [mv.group(1)]
                body = body[:mv.start()]
            expr = _to_math(body)
            return _ok(out, op, expr, var, f"{label}: {expr}" + (f" (variable {var[0]})" if var else ""))
    # sin verbo: si es una expresión válida se propone calcularla; con '=' se propone resolver
    expr = _to_math(raw)
    try:
        for part in re.split(r"[=;]", expr):
            normalize(parse(part))
    except Exception:
        out["summary"] = "No se reconoció la instrucción. Ejemplos: «deriva x al cubo por seno de x», «resuelve x^2-4=0», «límite de sin(x)/x cuando x tiende a 0»."
        return out
    op = "solve" if "=" in expr else "evaluate"
    r = _ok(out, op, expr, [], ("Resolver: " if op == "solve" else "Calcular: ") + expr)
    r["alternatives"] = ["simplify", "factor", "differentiate", "integrate"] if op == "evaluate" else []
    return r


def _ok(out, op, expr, var, summary):
    try:
        for part in re.split(r"[=;]|\bto\b", expr):
            if part.strip() and op not in ("units", "eigen", "matrix_det"): normalize(parse(part))
    except Exception as e:
        out["summary"] = f"Se entendió la operación ({summary}) pero la expresión no es válida: {getattr(e, 'message', e)}"
        out["operation"] = op
        out["expression"] = expr
        return out
    out.update({"understood": True, "operation": op, "expression": expr, "variables": var, "summary": summary})
    return out
