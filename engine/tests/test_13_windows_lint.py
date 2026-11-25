"""Lint de portabilidad a Windows: ninguna lectura/escritura de texto sin codificación explícita ni módulos solo-Unix."""
import os, re
RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SOLO_UNIX = ("fcntl", "resource", "pwd", "grp", "termios")


def _py():
    for d in ("math_universe_engine", "tools", "audit", "tests"):
        for r, _, fs in os.walk(os.path.join(RAIZ, d)):
            for f in fs:
                if f.endswith(".py") and f not in ("test_13_windows_lint.py", "test_06_seguridad_y_recursos.py"):
                    yield os.path.join(r, f)


def test_open_de_texto_con_encoding():
    mal = []
    for p in _py():
        for n, l in enumerate(open(p, encoding="utf-8"), 1):
            if re.search(r"\b(open|read_text|write_text)\(", l) and "encoding" not in l and not re.search(r"""['"][rwa]?b\+?['"]""", l) and not l.lstrip().startswith("#"):
                mal.append(f"{os.path.relpath(p, RAIZ)}:{n}: {l.strip()}")
    assert not mal, mal


def test_sin_modulos_solo_unix():
    mal = []
    for p in _py():
        for n, l in enumerate(open(p, encoding="utf-8"), 1):
            if re.match(r"\s*(import|from)\s+(" + "|".join(SOLO_UNIX) + r")\b", l):
                mal.append(f"{os.path.relpath(p, RAIZ)}:{n}")
    assert not mal, mal


def test_bat_son_ascii_y_crlf():
    d = os.path.join(RAIZ, "scripts")
    for f in os.listdir(d):
        if f.endswith(".bat"):
            b = open(os.path.join(d, f), "rb").read()
            b.decode("ascii")
            assert b.count(b"\n") == b.count(b"\r\n"), f
