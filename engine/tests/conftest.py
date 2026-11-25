import os, sys
# Las pruebas del motor propio no deben depender de que SymPy esté instalado: el respaldo SymPy se habilita solo en test_08/test_11.
os.environ["MATH_UNIVERSE_DISABLE_SYMPY"] = "1"
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import jsonschema, pytest
from math_universe_engine.dispatcher import handle, RESPONSE_SCHEMA


def call(**kw):
    r = handle(kw)
    jsonschema.validate(r, RESPONSE_SCHEMA)          # toda respuesta cumple el esquema
    return r


@pytest.fixture
def run():
    return call
