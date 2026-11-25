"""MATH UNIVERSE · módulo de álgebra lineal (AISLADO).

Componente independiente: NO modifica ni se registra en el motor estable (dispatcher, contrato JSON, operaciones existentes).
Reutiliza del motor, solo en lectura: parser seguro, constantes racionales, errores, plazo cooperativo y `solve.rref`.
NumPy NO es dependencia (solo lo usan las pruebas como oráculo)."""
__version__ = "0.1.1-aislado"
from .matrix import Matrix, parse_matrix_text          # noqa: E402,F401
from .api import run, OPERATIONS                         # noqa: E402,F401
