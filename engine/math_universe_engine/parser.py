"""Parser matemático seguro: tokenizador + Pratt parser propio.

Nunca usa eval/exec/sympify. Produce un AST de tuplas:
 ("num", Fraction) ("sym", nombre) ("bin", op, a, b) ("neg", a)
 ("call", nombre, [args]) ("fact", a)
Soporta multiplicación implícita (2x, 3(x+1), (a)(b)) y ^ o ** para potencia.
"""
import re
from fractions import Fraction
from .errors import ParseError, LimitExceeded

MAX_LEN = 5000
MAX_DEPTH = 100
_TOKEN = re.compile(r"\s*(?:(\d+\.?\d*(?:[eE][+-]?\d+)?|\.\d+(?:[eE][+-]?\d+)?)|([A-Za-z_][A-Za-z_0-9]*)|(\*\*|[-+*/^(),!]))")
CALLABLE_NAMES = None  # el evaluador valida nombres de función


def tokenize(text):
    if len(text) > MAX_LEN:
        raise LimitExceeded("Expresión demasiado larga", {"max": MAX_LEN})
    text = text.replace("×", "*").replace("÷", "/").replace("−", "-").replace(",", ",")
    pos, out = 0, []
    while pos < len(text):
        if text[pos:].strip() == "":
            break
        m = _TOKEN.match(text, pos)
        if not m:
            raise ParseError("Carácter no válido", {"position": pos, "char": text[pos:pos + 1].strip() or text[pos:pos + 2]})
        num, ident, op = m.groups()
        if num is not None:
            out.append(("num", num))
        elif ident is not None:
            out.append(("id", ident))
        else:
            out.append(("op", "^" if op == "**" else op))
        pos = m.end()
    return out


MAX_EXP10 = 1000  # H-1 (motor 0.4.0): sin cota, 1e999999999 colgaba el proceso e ignoraba timeout_ms


def _to_fraction(s):
    if "e" in s.lower():
        mant, exp = re.split(r"[eE]", s)
        if len(exp.lstrip("+-")) > 6 or abs(int(exp)) > MAX_EXP10:
            raise LimitExceeded("Exponente decimal fuera de rango", {"max_exponent": MAX_EXP10})
        return Fraction(mant) * Fraction(10) ** int(exp)
    return Fraction(s)


class _P:
    def __init__(self, toks):
        self.t, self.i, self.depth = toks, 0, 0

    def peek(self):
        return self.t[self.i] if self.i < len(self.t) else (None, None)

    def next(self):
        tok = self.peek()
        self.i += 1
        return tok

    def expect(self, v):
        k, x = self.next()
        if x != v:
            raise ParseError(f"Se esperaba '{v}'", {"token": self.i - 1})

    def parse(self):
        node = self.expr(0)
        if self.i != len(self.t):
            v = self.peek()[1]
            if v == ",":
                raise ParseError("Coma inesperada: use punto como separador decimal (1.5) y coma solo entre argumentos de funciones",
                                 {"token": self.i, "value": v})
            raise ParseError("Símbolo inesperado", {"token": self.i, "value": v})
        return node

    # precedencias: + - (10) * / y multiplicación implícita (20) unario (25) ^ (30, der.)
    def starts_atom(self):
        k, v = self.peek()
        return k in ("num", "id") or v == "("

    def expr(self, minp):
        self.depth += 1
        if self.depth > MAX_DEPTH:
            raise LimitExceeded("Anidamiento excesivo", {"max": MAX_DEPTH})
        k, v = self.peek()
        if k == "op" and v in "+-":
            self.next()
            operand = self.expr(25)
            left = ("neg", operand) if v == "-" else operand
        else:
            left = self.atom()
        while True:
            k, v = self.peek()
            if k == "op" and v == "!":
                self.next()
                if self.peek() == ("op", "!"):
                    raise ParseError("'!!' es ambiguo (factorial doble o factorial iterado): use paréntesis, por ejemplo (3!)!", {"token": self.i})
                left = ("fact", left); continue
            if k == "op" and v in ("+", "-") and minp <= 10:
                self.next(); left = ("bin", v, left, self.expr(11)); continue
            if k == "op" and v in ("*", "/") and minp <= 20:
                self.next(); left = ("bin", v, left, self.expr(21)); continue
            if k == "op" and v == "^" and minp <= 30:
                self.next(); left = ("bin", "^", left, self.expr(30)); continue
            if self.starts_atom() and minp <= 20:  # multiplicación implícita
                if self.t[self.i - 1][0] == "num" and self.peek()[0] == "num":
                    raise ParseError("Dos números seguidos sin operador (¿falta un operador o hay un punto de más?)",
                                     {"token": self.i})
                left = ("bin", "*", left, self.expr(21)); continue
            break
        self.depth -= 1
        return left

    def atom(self):
        k, v = self.next()
        if k == "num":
            return ("num", _to_fraction(v))
        if k == "id":
            if self.peek()[1] == "(":
                self.next()
                args = []
                if self.peek()[1] != ")":
                    args.append(self.expr(0))
                    while self.peek()[1] == ",":
                        self.next(); args.append(self.expr(0))
                self.expect(")")
                return ("call", v.lower(), args)
            return ("sym", v)
        if v == "(":
            inner = self.expr(0)
            self.expect(")")
            return inner
        raise ParseError("Expresión incompleta o símbolo inesperado", {"token": self.i - 1, "value": v})


def parse(text):
    if not isinstance(text, str) or not text.strip():
        raise ParseError("Expresión vacía")
    return _P(tokenize(text)).parse()
