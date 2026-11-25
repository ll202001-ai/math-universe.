"""Localiza el motor estable (fase 8) SIN modificarlo: solo añade su carpeta al final de sys.path si hace falta."""
import os, sys

_AQUI = os.path.dirname(os.path.abspath(__file__))
_RAIZ = os.path.dirname(_AQUI)


def candidatos():
    c = [os.environ.get("MATH_UNIVERSE_ENGINE_PATH")]
    for base in (_RAIZ, os.path.dirname(_RAIZ), os.path.dirname(os.path.dirname(_RAIZ))):
        c += [os.path.join(base, "engine"), os.path.join(base, "math_universe", "engine")]
    return [p for p in c if p]


def ruta_motor():
    for p in candidatos():
        if os.path.isfile(os.path.join(p, "math_universe_engine", "__init__.py")): return os.path.abspath(p)
    return None


def ensure():
    try:
        import math_universe_engine  # noqa: F401
        return
    except ImportError:
        pass
    p = ruta_motor()
    if p is None:
        raise ImportError("No se encuentra el motor estable (math_universe_engine). Descomprima la fase 8 junto a este paquete "
                          "(carpeta 'math_universe') o defina MATH_UNIVERSE_ENGINE_PATH=<ruta a la carpeta 'engine'>.")
    sys.path.append(p)
