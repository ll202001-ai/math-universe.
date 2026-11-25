"""Pruebas aleatorias con semilla fija: se genera un árbol de expresión con DOS representaciones
(texto para el motor, función Python para el oráculo). Cualquier discrepancia se reporta con su semilla."""
import math, random, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from audit.oraculo import run, val_text, close, fd

A_VAL = 1.7


def gen(rng, depth, funs=True):
    if depth == 0 or rng.random() < 0.25:
        r_ = rng.random()
        if r_ < 0.45: return "x", (lambda x: x)
        if r_ < 0.60: return "a", (lambda x: A_VAL)           # parámetro simbólico (cubre rutas con átomos paramétricos)
        k = rng.randint(-5, 5); return (f"({k})" if k < 0 else str(k)), (lambda x, k=k: float(k))
    op = rng.choice(["+", "-", "*", "/", "^", "f"] if funs else ["+", "-", "*", "/", "^"])
    if op == "f":
        name, fn = rng.choice([("sin", math.sin), ("cos", math.cos), ("exp", math.exp), ("atan", math.atan)])
        t, f = gen(rng, depth - 1, funs)
        return f"{name}({t})", (lambda x, f=f, fn=fn: fn(f(x)))
    if op == "^":
        t, f = gen(rng, depth - 1, funs)
        if rng.random() < 0.25:                               # exponente simbólico: (base)^a
            return f"({t})^a", (lambda x, f=f: f(x) ** A_VAL)
        k = rng.randint(2, 3)
        return f"({t})^{k}", (lambda x, f=f, k=k: f(x) ** k)
    a, fa = gen(rng, depth - 1, funs); b, fb = gen(rng, depth - 1, funs)
    fn = {"+": lambda x: fa(x) + fb(x), "-": lambda x: fa(x) - fb(x), "*": lambda x: fa(x) * fb(x), "/": lambda x: fa(x) / fb(x)}[op]
    return f"({a}){op}({b})", fn

def poly_gen(rng):
    deg = rng.randint(1, 6)
    cs = [rng.randint(-6, 6) for _ in range(deg + 1)]
    if cs[-1] == 0: cs[-1] = rng.choice([1, -2, 3])
    t = "+".join(f"({c})*x^{i}" for i, c in enumerate(cs) if c)
    return t or "0", (lambda x, cs=cs: sum(c * x**i for i, c in enumerate(cs)))

def main(n=400, seed=2024):
    rng = random.Random(seed)
    fails = []
    stats = {"simplify": 0, "diff": 0, "factor": 0, "expand": 0, "integral": 0, "unsupp": 0, "domain": 0}
    pts = [0.37, 0.91, 1.43, 2.17, -0.58, -1.29, 3.05]
    for i in range(n):
        t, f = gen(rng, rng.randint(1, 3))
        # simplify: el resultado debe coincidir numéricamente con el original donde ambos están definidos
        r = run(operation="simplify", expression=t)
        if r["status"] == "success_exact":
            stats["simplify"] += 1
            if r["verification"]["status"] == "failed": fails.append(("simplify-ver", t, r["exact_result"]))
            for x in pts:
                try: o = f(x)
                except Exception: continue
                if isinstance(o, complex) or abs(o) > 1e9 or o != o: continue
                try: m = val_text(r["exact_result"], x=x, a=A_VAL)
                except Exception as e: fails.append(("simplify-eval", t, r["exact_result"], str(e))); break
                if isinstance(m, complex) and abs(m.imag) < 1e-9: m = m.real
                if not close(o, m, 1e-6):
                    fails.append(("simplify-valor", t, r["exact_result"], x, o, m)); break
        elif r["status"] in ("unsupported",): stats["unsupp"] += 1
        elif r["status"] == "domain_error": stats["domain"] += 1
        elif r["status"] == "internal_error": fails.append(("internal", t, r.get("error")))
        # derivada
        d = run(operation="differentiate", expression=t, variables=["x"])
        if d["status"] == "success_exact":
            stats["diff"] += 1
            if d["verification"]["status"] == "failed": fails.append(("diff-ver", t, d["exact_result"]))
            for x in pts:
                try:
                    o = fd(f, x, 1e-4)
                    if isinstance(o, complex) or abs(o) > 1e6 or o != o: continue
                    if abs(f(x)) * 3.4e-11 > 1e-4 * (1 + abs(o)): continue      # redondeo del propio oráculo no informativo
                    m = val_text(d["exact_result"], x=x, a=A_VAL)
                except Exception: continue
                if isinstance(m, complex) and abs(m.imag) < 1e-9: m = m.real
                if not close(o, m, 1e-4):
                    fails.append(("diff-valor", t, d["exact_result"], x, o, m)); break
        elif d["status"] == "internal_error": fails.append(("internal-diff", t, d.get("error")))
    # polinomios: factor y expand
    for i in range(250):
        t, f = poly_gen(rng)
        r = run(operation="factor", expression=t)
        if r["status"] != "success_exact": fails.append(("factor-status", t, r["status"], r.get("error"))); continue
        stats["factor"] += 1
        if r["verification"]["status"] == "failed": fails.append(("factor-ver", t, r["exact_result"]))
        for x in pts:
            if not close(f(x), val_text(r["exact_result"], x=x), 1e-6): fails.append(("factor-valor", t, r["exact_result"], x)); break
        # producto aleatorio de factores lineales/cuadráticos -> expand debe coincidir
        a, b, c = rng.randint(-5, 5), rng.randint(-5, 5), rng.randint(1, 4)
        e = f"({a}+x)*({b}-{c}*x)*(x^2+{rng.randint(1,3)})"
        r2 = run(operation="expand", expression=e)
        stats["expand"] += 1
        if r2["status"] != "success_exact": fails.append(("expand-status", e, r2["status"])); continue
        for x in pts:
            if not close(val_text(e, x=x), val_text(r2["exact_result"], x=x), 1e-6): fails.append(("expand-valor", e, r2["exact_result"])); break
        # factor(expand(e)) debe ser equivalente
        r3 = run(operation="factor", expression=r2["exact_result"])
        if r3["status"] == "success_exact" and r3["verification"]["status"] == "failed": fails.append(("factor-expand-ver", e))
    # integrales de polinomios y racionales simples (derivar la primitiva debe devolver el integrando)
    for i in range(120):
        t, f = poly_gen(rng)
        if rng.random() < 0.5:
            k = rng.randint(1, 4); t2 = f"({t})/(x+{k})"; f2 = lambda x, f=f, k=k: f(x) / (x + k)
        else: t2, f2 = t, f
        r = run(operation="integrate", expression=t2, variables=["x"])
        if r["status"] == "unsupported": stats["unsupp"] += 1; continue
        if r["status"] != "success_exact": fails.append(("int-status", t2, r["status"], r.get("error"))); continue
        stats["integral"] += 1
        if r["verification"]["status"] == "failed": fails.append(("int-ver", t2, r["exact_result"]))
        for x in [0.4, 1.3, 2.6]:
            def prim(z):
                v = val_text(r["exact_result"].replace("+ C", ""), x=z)
                return v.real if isinstance(v, complex) else v
            try:
                a = fd(prim, x, 1e-4)
                if abs(prim(x)) * 3.4e-11 > 1e-4 * (1 + abs(a)): continue
            except Exception: continue
            if not close(a, f2(x), 1e-4): fails.append(("int-valor", t2, r["exact_result"], x, a, f2(x))); break
    return stats, fails

if __name__ == "__main__":
    st, fl = main()
    print(st)
    print("fallos:", len(fl))
    for x in fl[:25]: print(x)
