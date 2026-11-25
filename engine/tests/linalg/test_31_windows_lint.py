"""Portabilidad a Windows: nada de text-mode sin encoding ni módulos solo-Unix en el módulo nuevo."""
import os, re
from _soporte import RAIZ, recorrer


def _py():
    """Solo el código PROPIO del módulo de álgebra lineal: sus carpetas conocidas. Nunca .venv/site-packages (NumPy, jsonschema...) ni el motor."""
    for sub in ("math_universe_linalg", os.path.join("tests", "linalg")):  # los tests/tools del motor los cubre test_13_windows_lint
        yield from _py_en(os.path.join(RAIZ, sub))


def _py_en(base):
    for r, _, fs in recorrer(base):
        for f in fs:
            if f.endswith(".py") and f != "test_31_windows_lint.py": yield os.path.join(r, f)


def test_el_alcance_excluye_entornos_virtuales(tmp_path):
    (tmp_path / ".venv" / "Lib" / "site-packages" / "numpy").mkdir(parents=True)
    (tmp_path / ".venv" / "Lib" / "site-packages" / "numpy" / "malo.py").write_text("import fcntl\nopen('x')\n", encoding="utf-8")
    (tmp_path / "otro").mkdir(); (tmp_path / "otro" / "pyvenv.cfg").write_text("home=x", encoding="utf-8")
    (tmp_path / "otro" / "malo2.py").write_text("import pwd\n", encoding="utf-8")
    (tmp_path / "propio.py").write_text("x = 1\n", encoding="utf-8")
    vistos = [f for _, _, fs in recorrer(str(tmp_path)) for f in fs if f.endswith(".py")]
    assert vistos == ["propio.py"], vistos


def test_open_con_encoding_y_sin_modulos_unix():
    mal = []
    for p in _py():
        for n, l in enumerate(open(p, encoding="utf-8"), 1):
            if re.search(r"\b(open|read_text|write_text)\(", l) and "encoding" not in l and not re.search(r"""['"][rwa]?b\+?['"]""", l) and not l.lstrip().startswith("#"):
                mal.append(f"{os.path.relpath(p, RAIZ)}:{n}")
            if re.match(r"\s*(import|from)\s+(fcntl|resource|pwd|grp|termios)\b", l): mal.append(f"{os.path.relpath(p, RAIZ)}:{n} (solo Unix)")
    assert not mal, mal
