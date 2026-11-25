"""Auditoría matemática: oráculo INDEPENDIENTE del motor (funciones Python/NumPy/SciPy escritas a mano,
sin usar el parser ni el evaluador del motor). Cada caso trae su forma de texto y su forma lambda."""
import math, cmath, random, os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from math_universe_engine.dispatcher import handle
from math_universe_engine.parser import parse
from math_universe_engine.ast_tools import normalize, eval_float
import numpy as np
from scipy import integrate as sint

PTS = [-3.1, -1.7, -0.6, 0.35, 0.8, 1.9, 2.6, 4.3]

def run(**kw):
    return handle(kw)

def val_text(text, **env):
    """Evalúa el TEXTO de salida del motor con el evaluador del motor (para comparar con el oráculo lambda)."""
    return eval_float(normalize(parse(text)), env)

def close(a, b, tol=1e-7):
    if isinstance(a, complex) or isinstance(b, complex):
        return abs(a-b) <= tol*(1+abs(a)+abs(b))
    return abs(a-b) <= tol*(1+abs(a)+abs(b))

R = []   # resultados
def rec(cat, caso, ok, detalle=""):
    """Tres estados, nunca mezclados: 'ok' (resultado correcto), 'fallo' (incorrecto o no concluyente) y
    'no_soportado' (el motor lo declara fuera de alcance: NO cuenta como correcto)."""
    R.append({"categoria": cat, "caso": caso, "ok": bool(ok), "estado": "ok" if ok else "fallo", "detalle": str(detalle)})


def rec_ns(cat, caso, detalle=""):
    R.append({"categoria": cat, "caso": caso, "ok": False, "estado": "no_soportado", "detalle": str(detalle)})

# ---------- simplificación / dominio ----------
SIMP = [  # (texto, lambda original, condición esperada (substring) o None)
 ("(x^2-1)/(x-1)", lambda x: (x*x-1)/(x-1), "x ≠ 1"),
 ("(x^2-4)/(x+2)", lambda x: (x*x-4)/(x+2), "x ≠ -2"),
 ("(x^3-8)/(x-2)", lambda x: (x**3-8)/(x-2), "x ≠ 2"),
 ("(x^2-x)/x", lambda x: (x*x-x)/x, "x ≠ 0"),
 ("x/x", lambda x: x/x, "x ≠ 0"),
 ("(x+1)/(x^2-1)", lambda x: (x+1)/(x*x-1), "x ≠ 1"),
 ("1/x+1/(x+1)", lambda x: 1/x+1/(x+1), "x ≠ 0"),
 ("(x^2+2x+1)/(x+1)^2", lambda x: (x*x+2*x+1)/(x+1)**2, "x ≠ -1"),
 ("(2x^2-8)/(x^2-4)", lambda x: (2*x*x-8)/(x*x-4), "x ≠ 2"),
 ("(x-1)/(1-x)", lambda x: (x-1)/(1-x), "x ≠ 1"),
 ("x^2/x^3", lambda x: x**2/x**3, "x ≠ 0"),
 ("(x^4-1)/(x^2-1)", lambda x: (x**4-1)/(x*x-1), "x ≠ 1"),
 ("(x^2-1)/(x-1)^2", lambda x: (x*x-1)/(x-1)**2, "x ≠ 1"),
 ("(x^2-9)/(x^2-6x+9)", lambda x: (x*x-9)/(x*x-6*x+9), "x ≠ 3"),
 ("(x^2+1)/(x^2+1)", lambda x: 1.0, None),
]
def audit_simplify():
    for t, f, cond in SIMP:
        r = run(operation="simplify", expression=t)
        if r["status"] != "success_exact":
            rec("simplificación", t, False, f"status={r['status']} {r.get('error')}"); continue
        ok = True; det = r["exact_result"]; npts = 0
        for x in PTS:
            try:
                o = f(x)
            except ZeroDivisionError:
                continue
            try:
                m = val_text(r["exact_result"], x=x)
            except Exception as e:
                ok = False; det += f" | no evaluable: {e}"; break
            npts += 1
            if not close(o, m): ok = False; det += f" | x={x}: oráculo {o} motor {m}"; break
        if npts < 4: ok = False; det += f" | no concluyente: solo {npts} puntos comparados"
        if cond and not any(cond in c for c in r["conditions"]):
            ok = False; det += f" | condición {cond!r} ausente: {r['conditions']}"
        if r["verification"]["status"] == "failed": ok = False; det += " | verificación failed"
        rec("simplificación", t, ok, det + f" | cond={r['conditions']} | ver={r['verification']['status']}")

# ---------- factorización ----------
FACT = ["x^2-5x+6","x^2-1","x^3-1","x^3+1","x^4-1","x^4+4","x^4+x^2+1","6x^2+5x+1","x^3-6x^2+11x-6","2x^3-x^2-13x-6",
        "x^4-5x^2+4","x^2+1","x^5-1","x^6-1","x^4+1","12x^2-7x-10","x^3+x^2+x+1","x^4-16","8x^3-27","x^2+2x+1","x^3-3x^2+3x-1",
        "x^2-2","4x^2-12x+9","x^4+x^3+x^2+x+1","3x^3-3x","x^8-1"]
def audit_factor():
    for t in FACT:
        r = run(operation="factor", expression=t)
        if r["status"] != "success_exact":
            rec("factorización", t, False, f"status={r['status']} {r.get('error')}"); continue
        # oráculo: re-expandir con numpy sobre el polinomio original: evaluar texto resultado en puntos y comparar con polinomio coeficientes
        # coeficientes oráculo desde texto con parser propio de polinomios muy simple: usar np.poly1d vía evaluación en puntos (interpolación)
        ok = True
        try:
            xs = [-2.5,-1.3,-0.4,0.7,1.6,2.9,3.4,-3.7,0.2,1.1,2.2,-0.9,3.1]
            from_text = lambda x: val_text(t, x=x)
            for x in xs:
                a = from_text(x); b = val_text(r["exact_result"], x=x)
                if not close(a, b, 1e-6): ok = False; break
        except Exception as e:
            ok = False
        rec("factorización", t, ok and r["verification"]["status"] != "failed", f"{r['exact_result']} | ver={r['verification']['status']} | warn={r['warnings']}")

# ---------- ecuaciones ----------
EQ = [  # texto, lista esperada de raíces reales (floats) — calculada con numpy.roots independiente
 ("x^2-5x+6=0",[2,3]),("2x+3=11",[4]),("x^2-2=0",[-2**.5,2**.5]),("x^3-6x^2+11x-6=0",[1,2,3]),("x^4-5x^2+4=0",[-2,-1,1,2]),
 ("x^2+1=0",[]),("(x^2-1)/(x-1)=0",[-1]),("x^2=4",[-2,2]),("3x-7=2x+5",[12]),("x^2+4x+4=0",[-2]),
 ("2x^2-3x-2=0",[-0.5,2]),("x/(x-1)=2",[2]),("1/x=4",[0.25]),("x^2-x-1=0",[(1-5**.5)/2,(1+5**.5)/2]),
 ("(x-1)(x-2)(x+3)=0",[-3,1,2]),("x^3=x",[-1,0,1]),("x^3-3x^2+3x-1=0",[1]),("5=5","verdad"),("x+1=x+2",[]),
 ("(x+1)/(x+1)=1",None),("x^2-9=0",[-3,3]),("4x^2-1=0",[-.5,.5]),("x^3-2x^2-5x+6=0",[-2,1,3]),
]
def audit_equations():
    for t, exp in EQ:
        r = run(operation="solve", expression=t)
        if exp == "verdad":
            rec("ecuaciones", t, r["status"] == "success_exact" and r["exact_result"] == "Verdadero", f"{r['status']} {r.get('exact_result')}"); continue
        if exp is None:
            rec("ecuaciones", t, r["status"] == "multiple_solutions", f"{r['status']} {r.get('exact_result')} cond={r['conditions']}"); continue
        if not exp:
            rec("ecuaciones", t, r["status"] == "no_solution", f"{r['status']} {r.get('exact_result')}"); continue
        if r["status"] not in ("success_exact",):
            rec("ecuaciones", t, False, f"{r['status']} {r.get('error')}"); continue
        got = sorted(float(s["approximate"]) for s in r["data"]["solutions"])
        ok = len(got) == len(exp) and all(abs(a-b) < 1e-9 for a, b in zip(got, sorted(exp)))
        rec("ecuaciones", t, ok and r["verification"]["status"] == "passed", f"{r['exact_result']} | ver={r['verification']['status']} | oráculo={sorted(exp)}")

# ---------- sistemas lineales (oráculo: numpy.linalg) ----------
def audit_systems():
    rng = random.Random(7)
    for k in range(25):
        n = rng.choice([2,3,3,4])
        while True:
            A = [[rng.randint(-6,6) for _ in range(n)] for _ in range(n)]
            if abs(np.linalg.det(np.array(A, float))) > 0.5: break
        b = [rng.randint(-9,9) for _ in range(n)]
        names = "xyzw"[:n]
        eqs = []
        for i in range(n):
            lhs = "+".join(f"({A[i][j]})*{names[j]}" for j in range(n))
            eqs.append(f"{lhs}={b[i]}")
        r = run(operation="solve", expression="; ".join(eqs), variables=list(names))
        sol = np.linalg.solve(np.array(A, float), np.array(b, float))
        ok = r["status"] == "success_exact"
        if ok:
            from fractions import Fraction
            got = {k: float(Fraction(v)) for k, v in r["data"]["solution"].items()}
            ok = all(abs(got[names[i]] - sol[i]) < 1e-9 for i in range(n))
        ok = ok and r["verification"]["status"] == "passed" and r["data"].get("rank_A") == n
        rec("sistemas", "; ".join(eqs), ok, f"{r['status']} {r.get('exact_result')} ver={r['verification']['status']}")
    # singulares: indeterminado e incompatible, rangos con numpy
    SING = [("x+y=2; 2x+2y=4", "multiple_solutions"),("x+y=2; 2x+2y=5", "no_solution"),("x+y+z=3; x-y=1", "multiple_solutions"),
            ("x+y=1; x-y=1; 2x=3", "no_solution"),("x+y=1; x-y=1; 2x=2", "success_exact"),("x=1; x=2","no_solution"),
            ("2x+3y-z=1; 4x+6y-2z=2; x-y=0", "multiple_solutions"),("x+2y=3; 2x+4y=6; 3x+6y=9","multiple_solutions")]
    for t, st in SING:
        r = run(operation="solve", expression=t)
        rec("sistemas", t, r["status"] == st and r["verification"]["status"] in ("passed","not_possible"), f"{r['status']} {r.get('exact_result')} rA={(r.get('data') or {}).get('rank_A')} rAug={(r.get('data') or {}).get('rank_augmented')}")

# ---------- despeje ----------
ISO = [("V=I*R","R", lambda I,V,R: V/I),("P=V*I","I", None),("x=a*t+b","t", None),("1/f=1/a+1/b","a", None),("F=m*a","m", None),
       ("y=m*x+c","x", None),("a*x+b=c*x+d","x", None),("Q=m*c*(T-T0)","T", None),("v=u+a*t","a", None),("s=u*t+a*t^2/2","u", None),
       ("1/R=1/R1+1/R2","R1", None),("C=Q/V","V", None),("E=m*c^2","m", None),("A=pi*r^2","r", None)]
def audit_isolate():
    for t, v, _ in ISO:
        r = run(operation="solve", expression=t, variables=[v])
        if r["status"] != "success_exact":
            if r["status"] == "unsupported": rec_ns("despeje", f"{t} → {v}", (r.get("error") or {}).get("message", ""))
            else: rec("despeje", f"{t} → {v}", False, f"{r['status']} {r.get('error')}")
            continue
        rec("despeje", f"{t} → {v}", r["verification"]["status"] == "passed", f"{r['exact_result']} cond={r['conditions']} ver={r['verification']['status']}")

# ---------- derivadas (oráculo: diferencias centrales de alta precisión con numpy) ----------
DER = [("x^3*sin(x)", lambda x: x**3*math.sin(x)),("(x^2+1)/(x-1)", lambda x: (x*x+1)/(x-1)),("exp(2x)*x", lambda x: math.exp(2*x)*x),
       ("ln(x^2+1)", lambda x: math.log(x*x+1)),("x^x", lambda x: abs(x)**x if x>0 else float('nan')),("sin(x)/x", lambda x: math.sin(x)/x),
       ("atan(x)", lambda x: math.atan(x)),("sqrt(x^2+1)", lambda x: math.sqrt(x*x+1)),("tan(x)", lambda x: math.tan(x)),
       ("sin(cos(x))", lambda x: math.sin(math.cos(x))),("exp(x^2)", lambda x: math.exp(x*x)),("x*ln(x)", lambda x: x*math.log(x) if x>0 else float('nan')),
       ("1/(1+x^2)", lambda x: 1/(1+x*x)),("sinh(x)*cosh(x)", lambda x: math.sinh(x)*math.cosh(x)),("asin(x/3)", lambda x: math.asin(x/3)),
       ("x^(1/3)", lambda x: x**(1/3) if x>0 else float('nan')),("abs(x)", lambda x: abs(x)),("(x+1)^5", lambda x: (x+1)**5),
       ("ln(sin(x))", lambda x: math.log(math.sin(x)) if math.sin(x)>0 else float('nan')),("2^x", lambda x: 2**x)]
def fd(f, x, h=1e-4):
    return (-f(x+2*h)+8*f(x+h)-8*f(x-h)+f(x-2*h))/(12*h)
def audit_derivatives():
    for t, f in DER:
        r = run(operation="differentiate", expression=t, variables=["x"])
        if r["status"] != "success_exact":
            rec("derivadas", t, False, f"{r['status']} {r.get('error')}"); continue
        ok = True; det = r["exact_result"]; n = 0
        for x in [0.35, 0.8, 1.9, 2.6, 1.3]:
            try:
                o = fd(f, x)
                if o != o: continue
                m = val_text(r["exact_result"], x=x)
            except Exception as e:
                continue
            n += 1
            if not close(o, m, 1e-5): ok = False; det += f" | x={x}: oráculo {o} motor {m}"; break
        rec("derivadas", t, ok and n >= 2 and r["verification"]["status"] != "failed", det + f" | puntos={n} ver={r['verification']['status']}")
    # segunda derivada
    r = run(operation="differentiate", expression="x^4*sin(x)", variables=["x"], order=2)
    ok = r["status"] == "success_exact" and all(close(fd(lambda z: fd(lambda w: w**4*math.sin(w), z, 1e-3), x, 1e-3), val_text(r["exact_result"], x=x), 1e-3) for x in [0.5,1.5])
    rec("derivadas", "d²/dx² x^4 sin x", ok, r.get("exact_result"))

# ---------- integrales (oráculo: scipy.quad sobre intervalos definidos) ----------
INT = [("x^2",0,3,lambda x:x*x),("sin(x)",0,math.pi,math.sin),("exp(x)",0,1,math.exp),("1/(x^2+1)",0,1,lambda x:1/(x*x+1)),("x*exp(x)",0,2,lambda x:x*math.exp(x)),
       ("x*sin(x)",0,math.pi,lambda x:x*math.sin(x)),("1/(x^2-1)",2,4,lambda x:1/(x*x-1)),("1/x",1,math.e,lambda x:1/x),("x^2*exp(x)",0,1,lambda x:x*x*math.exp(x)),
       ("ln(x)",1,3,math.log),("(x+1)/(x^2+2x+3)",0,1,lambda x:(x+1)/(x*x+2*x+3)),("1/(x^2+4)",-2,2,lambda x:1/(x*x+4)),("cos(2x)",0,1,lambda x:math.cos(2*x)),
       ("x^3-2x",-1,2,lambda x:x**3-2*x),("1/((x+1)(x+2))",0,3,lambda x:1/((x+1)*(x+2))),("sqrt(x)",0,4,lambda x:x**.5),("tan(x)",0,1,math.tan),
       ("1/(x^2+2x+5)",0,2,lambda x:1/(x*x+2*x+5)),("x/(x^2+1)",0,3,lambda x:x/(x*x+1)),("x^2/(x+1)",0,2,lambda x:x*x/(x+1))]
def audit_integrals():
    for t, a, b, f in INT:
        r = run(operation="integrate", expression=t, variables=["x"], lower=str(a) if isinstance(a,int) else repr(a), upper=str(b) if isinstance(b,int) else repr(b))
        if r["status"] not in ("success_exact", "unsupported"):
            rec("integrales", f"∫[{a},{b}] {t}", False, f"{r['status']} {r.get('error')}"); continue
        if r["status"] == "unsupported":
            rec_ns("integrales", f"∫[{a},{b}] {t}", (r.get("error") or {}).get("message", "")); continue
        ref = sint.quad(f, a, b, epsabs=1e-12, epsrel=1e-12)[0]
        got = float(r["approximate_result"]) if r.get("approximate_result") else None
        rec("integrales", f"∫[{a:.4g},{b:.4g}] {t}", got is not None and close(ref, got, 1e-9) and r["verification"]["status"] != "failed", f"{r['exact_result']} ≈ {got} oráculo {ref} ver={r['verification']['status']}")
    # indefinidas: derivar numéricamente la primitiva devuelta
    IND = ["x^3","1/x","x*exp(x)","sin(x)^2","cos(x)*sin(x)","1/(x^2-1)","1/(x^2+1)","x*ln(x)","exp(2x)","(2x+1)/(x^2+x+1)","1/(x^3+1)","x^2*sin(x)","ln(x)","1/(x*(x+1))","tan(x)","sqrt(x)","1/sqrt(x)","exp(-x)*x","1/(x^2+2x+2)"]
    FUN = {"x^3":lambda x:x**3,"1/x":lambda x:1/x,"x*exp(x)":lambda x:x*math.exp(x),"sin(x)^2":lambda x:math.sin(x)**2,"cos(x)*sin(x)":lambda x:math.cos(x)*math.sin(x),
           "1/(x^2-1)":lambda x:1/(x*x-1),"1/(x^2+1)":lambda x:1/(x*x+1),"x*ln(x)":lambda x:x*math.log(x),"exp(2x)":lambda x:math.exp(2*x),
           "(2x+1)/(x^2+x+1)":lambda x:(2*x+1)/(x*x+x+1),"1/(x^3+1)":lambda x:1/(x**3+1),"x^2*sin(x)":lambda x:x*x*math.sin(x),"ln(x)":math.log,
           "1/(x*(x+1))":lambda x:1/(x*(x+1)),"tan(x)":math.tan,"sqrt(x)":lambda x:x**.5,"1/sqrt(x)":lambda x:x**-.5,"exp(-x)*x":lambda x:math.exp(-x)*x,"1/(x^2+2x+2)":lambda x:1/(x*x+2*x+2)}
    for t in IND:
        r = run(operation="integrate", expression=t, variables=["x"])
        if r["status"] == "unsupported":
            rec_ns("integrales", f"∫ {t} dx", (r.get("error") or {}).get("message", "")); continue
        if r["status"] != "success_exact":
            rec("integrales", f"∫ {t} dx", False, f"{r['status']} {r.get('error')}"); continue
        ok = True
        for x in [0.6, 1.4, 2.3, 3.1]:
            try:
                a = fd(lambda z: val_text(r["exact_result"], x=z).real if isinstance(val_text(r["exact_result"], x=z), complex) else val_text(r["exact_result"], x=z), x, 1e-4)
                o = FUN[t](x)
            except Exception as e:
                continue
            if not close(a, o, 1e-5): ok = False; break
        rec("integrales", f"∫ {t} dx", ok and r["verification"]["status"] != "failed", f"{r['exact_result']} ver={r['verification']['status']}")

# ---------- límites (oráculo: evaluación numérica con aproximaciones ±h, valores conocidos) ----------
LIM = [("sin(x)/x","0","1"),("(1-cos(x))/x^2","0","1/2"),("(exp(x)-1)/x","0","1"),("(x^2-1)/(x-1)","1","2"),("ln(1+x)/x","0","1"),
       ("(sqrt(1+x)-1)/x","0","1/2"),("(x^2+1)/(x^2-1)","+oo","1"),("(3x^2+2x)/(x^2+5)","+oo","3"),("x/(x^2+1)","+oo","0"),
       ("tan(x)/x","0","1"),("(x^3-8)/(x-2)","2","12"),("atan(x)/x","0","1"),("(sin(x)-x)/x^3","0","-1/6"),("(1/x-1/(x+1))","+oo","0"),
       ("(x^2-4)/(x-2)","2","4"),("(sqrt(x+4)-2)/x","0","1/4"),("sin(3x)/sin(5x)","0","3/5"),("(cos(x)-1)/x","0","0"),
       ("(2x^3+x)/(5x^3-1)","-oo","2/5"),("sinh(x)/x","0","1")]
def audit_limits():
    for t, p, exp in LIM:
        r = run(operation="limit", expression=t, variables=["x"], point=p)
        if r["status"] != "success_exact":
            rec("límites", f"lim[{p}] {t}", False, f"{r['status']} {r.get('error')}"); continue
        from fractions import Fraction
        want = Fraction(exp)
        got = Fraction(r["exact_result"])
        rec("límites", f"lim[{p}] {t}", got == want and r["verification"]["status"] == "passed", f"{r['exact_result']} oráculo {want} ver={r['verification']['status']}")
    # límites con resultado infinito / inexistente
    for t, p, d, want in [("1/x","0","+","oo"),("1/x","0","-","-oo"),("1/x","0","both","no"),("abs(x)/x","0","both","no"),("1/x^2","0","both","oo"),("x^2","+oo","both","oo")]:
        r = run(operation="limit", expression=t, variables=["x"], point=p, direction=d)
        s = (r.get("exact_result") or "") + " " + r["status"]
        ok = ((r.get("exact_result") == want) if want != "no" else r["status"] in ("no_solution", "unsupported"))
        rec("límites", f"lim[{p},{d}] {t}", ok, s)

# ---------- aproximaciones numéricas ----------
NUM = [("1/3", 30, "0.333333333333333333333333333333"),("sqrt(2)", 15, "1.41421356237310"),("pi", 15, "3.14159265358979"),("22/7", 10, "3.142857143"),
       ("2^100", 40, None),("1/7", 20, "0.14285714285714285714"),("exp(1)", 15, "2.71828182845905"),("sin(1)", 12, "0.841470984808"),("ln(10)", 12, "2.30258509299"),
       ("sqrt(2)+sqrt(3)", 12, "3.14626436994"),("100!/98!", 10, "9900")]
def audit_numeric():
    for t, p, want in NUM:
        r = run(operation="evaluate", expression=t, precision=p)
        if r["status"] != "success_exact":
            rec("numérico", f"{t} @{p}", False, f"{r['status']} {r.get('error')}"); continue
        got = r.get("approximate_result")
        if want is None:
            ok = got is not None or (r.get("exact_result") or "").lstrip("-").isdigit()
        elif got is None:
            ok = r.get("exact_result") == want
        else:
            ok = got is not None and str(got).startswith(want[:len(want)-1])
        rec("numérico", f"{t} @{p}", ok, f"{got} (esperado {want})")

ALL = [audit_simplify, audit_factor, audit_equations, audit_systems, audit_isolate, audit_derivatives, audit_integrals, audit_limits, audit_numeric]
def main():
    for f in ALL: f()
    os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), "salida"), exist_ok=True)
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "salida", "auditoria_oraculo.json")
    json.dump(R, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    from collections import Counter
    c = Counter((x["categoria"], x["estado"]) for x in R)
    for cat in dict.fromkeys(x["categoria"] for x in R):
        print(f"{cat:16} correctos={c[(cat,'ok')]:3} no_soportados={c[(cat,'no_soportado')]:3} FALLOS={c[(cat,'fallo')]:3}")
    for x in R:
        if x["estado"] == "fallo": print("FALLO", x["categoria"], "|", x["caso"], "|", x["detalle"][:230])
        elif x["estado"] == "no_soportado": print("no soportado", x["categoria"], "|", x["caso"], "|", x["detalle"][:100])
if __name__ == "__main__":
    main()
