"""Matriz exacta sobre Q (Fraction) y lectura segura de entradas."""
import re
from fractions import Fraction
from . import _motor
_motor.ensure()
from math_universe_engine.errors import InvalidRequest, MathDomainError, ParseError   # reutilizado
from math_universe_engine.parser import parse                                           # reutilizado (parser seguro, sin eval)
from math_universe_engine.ast_tools import normalize, const_value                       # reutilizado (constantes racionales)

MAX_DIM = 40
MAX_TEXT = 20000
_ENTERO_O_DEC = re.compile(r"[+-]?\d{1,60}(\.\d{1,60})?")
_FRAC = re.compile(r"([+-]?\d{1,60})\s*/\s*(\d{1,60})")
_CIENT = re.compile(r"[+-]?\d{1,30}(\.\d{1,30})?[eE][+-]?\d{1,2}")


def fr(x):
    return str(x.numerator) if x.denominator == 1 else f"{x.numerator}/{x.denominator}"


def entry(v):
    """Convierte una entrada a Fraction EXACTA. Acepta int, Fraction, float finito (por su texto decimal), y texto:
    '3', '-2.5', '7/3' o cualquier constante racional que el parser del motor sepa evaluar ('(1+2)/6', '2*3')."""
    if isinstance(v, bool): raise InvalidRequest("Una entrada no puede ser booleana")
    if isinstance(v, int): return Fraction(v)
    if isinstance(v, Fraction): return v
    if isinstance(v, float):
        if v != v or v in (float("inf"), float("-inf")): raise InvalidRequest("Entrada no finita")
        return Fraction(repr(v))
    if not isinstance(v, str): raise InvalidRequest(f"Tipo de entrada no soportado: {type(v).__name__}")
    s = v.strip()
    if not s or len(s) > 200: raise ParseError("Entrada vacía o demasiado larga")
    if _ENTERO_O_DEC.fullmatch(s): return Fraction(s)
    m = _FRAC.fullmatch(s)
    if m:
        if int(m.group(2)) == 0: raise MathDomainError("División por cero en una entrada de la matriz")
        return Fraction(int(m.group(1)), int(m.group(2)))
    if _CIENT.fullmatch(s): return Fraction(s)                         # notación científica acotada (|exponente| ≤ 99): exacta y barata
    # PROTECCIÓN: el parser del motor estable no acota los literales numéricos (p. ej. '1e999999999' lo deja colgado ignorando timeout_ms;
    # hallazgo H-1 de docs/INFORME_ALGEBRA_LINEAL.md). Este módulo no puede modificarlo, así que filtra ANTES de delegarle.
    if re.search(r"[eE]\s*[+-]?\s*\d{3,}", s) or re.search(r"\d{61,}", s):
        raise ParseError("Literal numérico demasiado grande (exponente de 3+ cifras o más de 60 dígitos)")
    try:
        q = const_value(normalize(parse(s)))
    except MathDomainError:
        raise
    except Exception as e:
        raise ParseError(f"Entrada no válida: '{s}'") from e
    if q is None: raise ParseError(f"La entrada '{s}' no es una constante racional exacta (esta versión no admite símbolos ni irracionales)")
    return Fraction(q)


class Matrix:
    __slots__ = ("rows", "nr", "nc")

    def __init__(self, rows):
        rows = [list(r) for r in rows]
        if not rows or not rows[0]: raise InvalidRequest("La matriz no puede estar vacía")
        nc = len(rows[0])
        if any(len(r) != nc for r in rows): raise InvalidRequest("Todas las filas deben tener el mismo número de columnas")
        if len(rows) > MAX_DIM or nc > MAX_DIM: raise InvalidRequest(f"Dimensión máxima {MAX_DIM}×{MAX_DIM}")
        self.rows = tuple(tuple(entry(x) for x in r) for r in rows)
        self.nr, self.nc = len(rows), nc

    @property
    def shape(self): return (self.nr, self.nc)

    def is_square(self): return self.nr == self.nc

    def __eq__(self, o): return isinstance(o, Matrix) and self.rows == o.rows

    def __hash__(self): return hash(self.rows)

    def tolist(self): return [list(r) for r in self.rows]

    def to_strings(self): return [[fr(x) for x in r] for r in self.rows]

    def __str__(self):
        w = max(len(fr(x)) for r in self.rows for x in r)
        return "\n".join("[ " + "  ".join(fr(x).rjust(w) for x in r) + " ]" for r in self.rows)

    def __repr__(self): return "Matrix(" + repr(self.to_strings()) + ")"

    @staticmethod
    def identity(n):
        return Matrix([[1 if i == j else 0 for j in range(n)] for i in range(n)])


def _split_top(s):
    out, depth, cur = [], 0, []
    for ch in s:
        if ch in "[(": depth += 1
        elif ch in "])":
            depth -= 1
            if depth < 0: raise ParseError("Corchetes o paréntesis desbalanceados")
        if ch == "," and depth == 0: out.append("".join(cur)); cur = []
        else: cur.append(ch)
    if depth != 0: raise ParseError("Corchetes o paréntesis desbalanceados")
    out.append("".join(cur))
    return out


def parse_matrix_text(text):
    """'[[1,2],[3,4]]' -> Matrix. Las entradas se leen con `entry` (racionales exactos)."""
    if not isinstance(text, str) or len(text) > MAX_TEXT: raise InvalidRequest("Texto de matriz inválido o demasiado largo")
    s = text.strip()
    if not (s.startswith("[") and s.endswith("]")): raise ParseError("Una matriz se escribe como [[a,b],[c,d]]")
    filas = _split_top(s[1:-1])
    rows = []
    for f in filas:
        f = f.strip()
        if not (f.startswith("[") and f.endswith("]")): raise ParseError("Cada fila debe ir entre corchetes: [[1,2],[3,4]]")
        rows.append([e for e in _split_top(f[1:-1])])
    return Matrix(rows)


def as_matrix(x):
    if isinstance(x, Matrix): return x
    if isinstance(x, str): return parse_matrix_text(x)
    if isinstance(x, (list, tuple)):
        if x and not isinstance(x[0], (list, tuple)): return Matrix([[e] for e in x])      # vector plano -> columna
        return Matrix(x)
    raise InvalidRequest("Matriz no reconocida (use lista de filas o texto [[...],[...]])")
