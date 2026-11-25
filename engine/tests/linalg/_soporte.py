import os, sys
RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # carpeta engine/
sys.path.insert(0, RAIZ)
from math_universe_linalg import _motor
_motor.ensure()
EXCLUIDOS = {"__pycache__", ".pytest_cache", ".venv", "venv", "env", ".git", "site-packages", "node_modules", "build", "dist"}


def recorrer(base):
    """os.walk que NO entra en entornos virtuales, dependencias instaladas ni cachés (no son código ni del motor ni del módulo)."""
    for r, ds, fs in os.walk(base):
        ds[:] = [d for d in ds if d not in EXCLUIDOS and not d.endswith(".egg-info") and not os.path.isfile(os.path.join(r, d, "pyvenv.cfg"))]
        yield r, ds, fs


from fractions import Fraction
import random
import pytest
import math_universe_linalg as L
from math_universe_linalg.matrix import Matrix


def M(x): return L.matrix.as_matrix(x) if hasattr(L, "matrix") else Matrix(x)


def F(s): return Fraction(s)


def run(op, a=None, b=None, **k): return L.run(op, a, b, **k)


def rnd_matrix(rng, n, m, lo=-9, hi=9, frac=False):
    if frac: return Matrix([[Fraction(rng.randint(lo, hi), rng.randint(1, 6)) for _ in range(m)] for _ in range(n)])
    return Matrix([[rng.randint(lo, hi) for _ in range(m)] for _ in range(n)])


def to_np(a):
    np = pytest.importorskip("numpy")
    return np.array([[float(x) for x in r] for r in a.rows])
