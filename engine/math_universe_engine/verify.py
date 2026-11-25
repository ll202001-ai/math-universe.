"""Verificación independiente: se evalúa el ORIGINAL (AST) y el RESULTADO re-analizado desde su texto,
con rutas de evaluación distintas a las del algoritmo que produjo el resultado."""
import math
import random
from fractions import Fraction
from .ast_tools import eval_q, eval_float, free_symbols, normalize
from .errors import MathDomainError, NotImplementedOperation, ParseError
from .parser import parse
from .qsqrt import Q


def sample_env(syms, assumptions, rng):
    env = {}
    for s in syms:
        v = Fraction(rng.randint(1, 15), rng.randint(1, 6)) * rng.choice([1, -1])
        a = (assumptions or {}).get(s)
        if a == "positive": v = abs(v)
        elif a == "negative": v = -abs(v)
        elif a == "integer": v = Fraction(rng.randint(-9, 9))
        env[s] = v
    return env


def equivalent(orig, res_text, assumptions=None, need=3, tries=60):
    try:
        res = normalize(parse(res_text))
    except Exception:
        return "not_possible"
    syms = sorted((free_symbols(orig) | free_symbols(res)))
    rng = random.Random(2024); ok = 0
    for _ in range(tries):
        env = sample_env(syms, assumptions, rng)
        try:
            try:
                a, b = eval_q(orig, env), eval_q(res, env)
                same = (a == b)
            except NotImplementedOperation:
                fa, fb = eval_float(orig, env), eval_float(res, env)
                same = abs(fa - fb) <= 1e-9 * (1 + abs(fa))
        except (MathDomainError, ZeroDivisionError, ValueError, OverflowError, NotImplementedOperation):
            continue
        if not same: return "failed"
        ok += 1
        if ok >= need + 5: break
    return "passed" if ok >= need else "not_possible"
