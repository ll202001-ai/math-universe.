"""Límites de recursos: plazo cooperativo (timeout_ms) y tope de tamaño de resultados.

El plazo se comprueba dentro de los bucles del motor propio (multiplicación de
polinomios, división, Gauss, factorización...). Para el backend SymPy, que no
se puede interrumpir cooperativamente, ver `run_hard_timeout`.
"""
import sys
import threading
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


def _procesos_disponibles():
    """Android (Chaquopy) no permite crear procesos hijo: multiprocessing lanza OSError (CI 2026-11-25)."""
    return not hasattr(sys, "getandroidapilevel")


def run_in_thread(func, args, timeout_s):
    """Alternativa sin procesos: func en un hilo con el mismo plazo. Si se agota, se informa TimeoutExceeded y el
    resultado tardío se descarta (el hilo no se puede matar: limitación documentada en docs/LIMITACIONES.md)."""
    box = {}

    def run():
        try:
            box["ok"] = func(*args)
        except BaseException as e:  # se informa igual que desde el proceso hijo
            box["err"] = repr(e)
            box["exc"] = e

    t = threading.Thread(target=run, name="mu_sympy", daemon=True)
    t.start()
    t.join(timeout_s)
    if t.is_alive():
        raise TimeoutExceeded("Se agotó el tiempo de cálculo permitido (el cálculo se descartó)")
    if "err" in box:
        from .errors import EngineError
        if isinstance(box.get("exc"), EngineError): raise box["exc"]   # errores del contrato: se conservan tal cual
        raise RuntimeError(box["err"])
    return box["ok"]


def run_hard_timeout(func, args, timeout_s):
    """Ejecuta func(*args) en un proceso hijo y lo termina si excede el plazo. Donde no hay procesos (Android), o si el
    proceso no se puede crear, usa run_in_thread."""
    if not _procesos_disponibles():
        return run_in_thread(func, args, timeout_s)
    try:
        ctx = mp.get_context("spawn")
        q = ctx.Queue()
        p = ctx.Process(target=_child, args=(q, func, args))
        p.start()
    except (OSError, ImportError, NotImplementedError, ValueError):
        return run_in_thread(func, args, timeout_s)
    try:
        kind, val = q.get(timeout=timeout_s)
    except Exception:
        p.terminate(); p.join(2)
        raise TimeoutExceeded("Se agotó el tiempo de cálculo permitido (proceso terminado)")
    p.join(2)
    if kind == "err":
        raise RuntimeError(val)
    return val
