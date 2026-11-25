"""Límites de recursos: plazo cooperativo (timeout_ms) y tope de tamaño de resultados.

El plazo se comprueba dentro de los bucles del motor propio (multiplicación de
polinomios, división, Gauss, factorización...). Para el backend SymPy, que no
se puede interrumpir cooperativamente, ver `run_hard_timeout`.
"""
import time
import multiprocessing as mp
from .errors import TimeoutExceeded, LimitExceeded

MAX_TERMS = 20000
MAX_DEGREE = 2000
MAX_POW = 500
DEFAULT_TIMEOUT_MS = 10000

_deadline = None
_counter = 0


def start(timeout_ms):
    global _deadline, _counter
    _deadline = time.perf_counter() + (timeout_ms if timeout_ms else DEFAULT_TIMEOUT_MS) / 1000.0
    _counter = 0


def stop():
    global _deadline
    _deadline = None


def check():
    if _deadline is not None and time.perf_counter() > _deadline:
        raise TimeoutExceeded("Se agotó el tiempo de cálculo permitido")


def check_size(n_terms):
    if n_terms > MAX_TERMS:
        raise LimitExceeded("Resultado demasiado grande", {"max_terms": MAX_TERMS})


def _child(q, func, args):
    try:
        q.put(("ok", func(*args)))
    except BaseException as e:  # pragma: no cover
        q.put(("err", repr(e)))


def run_hard_timeout(func, args, timeout_s):
    """Ejecuta func(*args) en un proceso hijo y lo termina si excede el plazo."""
    ctx = mp.get_context("spawn")
    q = ctx.Queue()
    p = ctx.Process(target=_child, args=(q, func, args))
    p.start()
    try:
        kind, val = q.get(timeout=timeout_s)
    except Exception:
        p.terminate(); p.join(2)
        raise TimeoutExceeded("Se agotó el tiempo de cálculo permitido (proceso terminado)")
    p.join(2)
    if kind == "err":
        raise RuntimeError(val)
    return val
