"""Motor 0.5.0: aproximación de precisión arbitraria con mpmath (contrastada con la evaluación en coma flotante)."""
import pytest

from math_universe_engine.dispatcher import handle
from math_universe_engine import numeric_mp

mpmath = pytest.importorskip("mpmath")

# Valores de referencia publicados (tablas de constantes), no calculados con el propio motor.
PI_50 = "3.1415926535897932384626433832795028841971693993751"
E_40 = "2.718281828459045235360287471352662497757"
SQRT2_40 = "1.414213562373095048801688724209698078570"


def _ap(expr, p):
    r = handle({"operation": "evaluate", "expression": expr, "precision": p})
    assert r["status"] == "success_exact", r
    return r


def test_pi_50_cifras():
    r = _ap("pi", 50)
    assert r["exact_result"] == "pi"                      # lo exacto se conserva
    assert r["approximate_result"] == PI_50
    assert not any("mpmath" in w for w in r["warnings"])


def test_e_40_cifras():
    assert _ap("e", 40)["approximate_result"] == E_40


def test_radical_cuadratico_sigue_con_aritmetica_entera():
    assert _ap("sqrt(2)", 40)["approximate_result"] == SQRT2_40


def test_15_cifras_o_menos_no_cambia_el_comportamiento():
    assert _ap("pi", 10)["approximate_result"] == "3.141592654"


def test_expresion_trascendente_compuesta():
    r = _ap("ln(10)", 30)
    assert r["approximate_result"].startswith("2.30258509299404568401799145468")


def test_contraste_independiente_rechaza_un_valor_incoherente(monkeypatch):
    """Si mpmath diera un valor distinto del de coma flotante, no se entrega (se cae a ~15 cifras con aviso)."""
    monkeypatch.setattr(numeric_mp, "_ev", lambda n, mp: mp.mpf(3))
    r = _ap("pi", 40)
    assert r["approximate_result"].startswith("3.14159265358979")
    assert len(r["approximate_result"].replace(".", "")) <= 16
    assert any("15 cifras" in w for w in r["warnings"])


def test_sin_mpmath_aviso_y_15_cifras(monkeypatch):
    monkeypatch.setattr(numeric_mp, "mpmath", None)
    r = _ap("pi", 40)
    assert r["approximate_result"] == "3.14159265358979"
    assert any("15 cifras" in w for w in r["warnings"])


def test_capacidades_informan_dependencias_reales():
    d = handle({"operation": "capabilities"})["data"]["dependencies"]
    assert d["mpmath"] == mpmath.__version__ and d["python"]
