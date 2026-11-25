"""Motor 0.5.0: el respaldo SymPy funciona donde no se pueden crear procesos hijo (Android/Chaquopy).
En el emulador Android, multiprocessing lanzaba OSError y la integral de sin(x)^2 fallaba (CI 2026-11-25)."""
import sys
import time

import pytest

from math_universe_engine import limits
from math_universe_engine.dispatcher import handle
from math_universe_engine.errors import TimeoutExceeded

pytest.importorskip("sympy")


@pytest.fixture(autouse=True)
def _sympy_activo(monkeypatch):
    monkeypatch.delenv("MATH_UNIVERSE_DISABLE_SYMPY", raising=False)   # conftest lo desactiva por defecto


def _sin_procesos(monkeypatch):
    def no(*a, **k):
        raise OSError("multiprocessing no disponible (simulado)")
    monkeypatch.setattr(limits.mp, "get_context", no)


def test_sympy_sin_procesos_hijo_da_el_mismo_resultado_verificado(monkeypatch):
    _sin_procesos(monkeypatch)
    r = handle({"operation": "integrate", "expression": "sin(x)^2", "timeout_ms": 60000})
    assert r["status"] == "success_exact", r
    assert r["method"] == "sympy_respaldo_experimental" and r["verification"]["status"] == "passed"
    assert r["exact_result"] == "x/2 - sin(x)*cos(x)/2 + C"


def test_android_usa_hilo_sin_intentar_procesos(monkeypatch):
    monkeypatch.setattr(sys, "getandroidapilevel", lambda: 34, raising=False)
    _sin_procesos(monkeypatch)   # si se intentara crear un proceso, fallaría con OSError
    assert limits._procesos_disponibles() is False
    r = handle({"operation": "integrate", "expression": "sin(x)^2", "timeout_ms": 60000})
    assert r["status"] == "success_exact" and r["verification"]["status"] == "passed"


def test_hilo_respeta_el_plazo():
    t0 = time.perf_counter()
    with pytest.raises(TimeoutExceeded):
        limits.run_in_thread(time.sleep, (5,), 0.3)
    assert time.perf_counter() - t0 < 2


def test_hilo_propaga_errores_como_el_proceso():
    with pytest.raises(RuntimeError, match="ZeroDivisionError"):
        limits.run_in_thread(lambda: 1 / 0, (), 5)
