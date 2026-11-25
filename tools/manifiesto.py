"""Manifiesto SHA-256 de TODO el paquete.   python tools/manifiesto.py --generar | (sin argumentos: verifica)"""
import hashlib, os, sys
RAIZ = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
MAN = os.path.join(RAIZ, "MANIFIESTO_SHA256.txt")
EXCL = {"__pycache__", ".pytest_cache", ".venv", ".dart_tool", "build"}


def archivos():
    for r, ds, fs in os.walk(RAIZ):
        ds[:] = sorted(d for d in ds if d not in EXCL)
        for f in sorted(fs):
            rel = os.path.relpath(os.path.join(r, f), RAIZ).replace(os.sep, "/")
            if rel != "MANIFIESTO_SHA256.txt" and not f.endswith(".pyc"): yield rel


def h(rel):
    with open(os.path.join(RAIZ, rel), "rb") as f: return hashlib.sha256(f.read()).hexdigest()


def main():
    if "--generar" in sys.argv:
        with open(MAN, "w", encoding="utf-8", newline="\n") as f:
            for rel in archivos(): f.write(f"{h(rel)}  {rel}\n")
        print("manifiesto escrito"); return 0
    with open(MAN, encoding="utf-8") as f:
        esp = dict(l.rstrip("\n").split("  ", 1)[::-1] for l in f if l.strip())
    act = set(archivos())
    falta, sobra = sorted(set(esp) - act), sorted(act - set(esp))
    mal = sorted(r for r in esp if r in act and h(r) != esp[r])
    for t, l in (("FALTAN", falta), ("NO LISTADOS", sobra), ("MODIFICADOS", mal)):
        for r in l: print(t, r)
    ok = not (falta or sobra or mal)
    print(f"{len(esp)} archivos en el manifiesto -> {'INTEGRO' if ok else 'CON DIFERENCIAS'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
