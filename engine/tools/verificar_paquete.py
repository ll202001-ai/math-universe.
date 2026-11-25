"""Genera o verifica MANIFIESTO_SHA256.txt (hash de cada archivo del paquete).
Uso:  python tools/verificar_paquete.py --generar   |   python tools/verificar_paquete.py   (verifica)"""
import hashlib, os, sys
RAIZ = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
MAN = os.path.join(RAIZ, "MANIFIESTO_SHA256.txt")
EXCL = {"__pycache__", ".pytest_cache", ".venv", "validacion", "salida"}


def archivos():
    for r, ds, fs in os.walk(RAIZ):
        ds[:] = sorted(d for d in ds if d not in EXCL)
        for f in sorted(fs):
            p = os.path.join(r, f)
            rel = os.path.relpath(p, RAIZ).replace(os.sep, "/")
            if rel != "MANIFIESTO_SHA256.txt" and not f.endswith(".pyc"):
                yield rel, p


def h(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def main():
    if "--generar" in sys.argv:
        with open(MAN, "w", encoding="utf-8", newline="\n") as f:
            for rel, p in archivos():
                f.write(f"{h(p)}  {rel}\n")
        print("manifiesto escrito")
        return 0
    esp = {}
    with open(MAN, encoding="utf-8") as f:
        for l in f:
            if l.strip():
                s, rel = l.rstrip("\n").split("  ", 1)
                esp[rel] = s
    act = {rel: p for rel, p in archivos()}
    falta = sorted(set(esp) - set(act)); sobra = sorted(set(act) - set(esp))
    mal = sorted(r for r in esp if r in act and h(act[r]) != esp[r])
    for t, l in (("FALTAN", falta), ("NO LISTADOS", sobra), ("MODIFICADOS", mal)):
        for r in l:
            print(t, r)
    ok = not (falta or sobra or mal)
    print(f"{len(esp)} archivos en el manifiesto -> {'INTEGRO' if ok else 'CON DIFERENCIAS'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
