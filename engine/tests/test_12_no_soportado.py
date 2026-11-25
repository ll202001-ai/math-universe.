"""El catálogo de lo NO soportado se ejecuta de verdad y la documentación debe coincidir con el comportamiento real."""
import os, sys
import pytest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import audit.no_soportado as ns

A, B = ns.ejecutar()
os.environ["MATH_UNIVERSE_DISABLE_SYMPY"] = "1"


@pytest.mark.parametrize("x", A, ids=lambda x: f"{x['op']}:{x['expr']}")
def test_no_soportado_no_entrega_resultado(x):
    assert x["status"] == "unsupported", x                    # ni éxito ni error interno: una limitación declarada
    assert not x["devolvio_resultado"]
    assert x["mensaje"]


@pytest.mark.parametrize("x", B, ids=lambda x: f"{x['op']}:{x['expr']}")
def test_incompleto_se_comporta_como_se_documenta(x):
    assert x["cumple"], x


def test_documento_no_soportado_esta_al_dia():
    ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "docs", "NO_SOPORTADO.md")
    with open(ruta, encoding="utf-8", newline="") as f:
        actual = f.read().replace("\r\n", "\n")
    assert actual == ns.generar_markdown(), "docs/NO_SOPORTADO.md está desactualizado: ejecute  python tools/generar_no_soportado.py"
