"""Prepara el proyecto Android generado por `flutter create` para ejecutar el motor Python con Chaquopy.
Uso: python tools/ci/patch_android.py <carpeta app> <carpeta engine>
Hace: copia motor + puente a android/app/src/main/python, instala MainActivity.kt y anade el plugin Chaquopy
(soporta Gradle Kotlin DSL y Groovy) con SymPy y mpmath empaquetados en el APK (sin red en tiempo de ejecucion), minSdk >= 24
(requisito de Chaquopy) y ABIs arm64-v8a + x86_64. Falla con mensaje claro si no reconoce el formato (no deja un APK sin motor).
Versiones: Chaquopy 17.2.0 admite Android Gradle Plugin >= 7.3 (Flutter 3.50 genera AGP 9.3) y Python 3.10-3.15."""
import os, re, shutil, sys

CHAQUOPY = "17.2.0"
PYVER = "3.12"
# Dependencias puras de Python del motor dentro del APK. Mismas versiones que el Python embebido de Windows (engine/requirements-lock.txt).
PIP = ("sympy==1.14.0", "mpmath==1.3.0")


def leer(p):
    with open(p, encoding="utf-8") as f: return f.read()


def escribir(p, s):
    with open(p, "w", encoding="utf-8", newline="\n") as f: f.write(s)


def main(app, engine):
    android = os.path.join(app, "android")
    py_dst = os.path.join(android, "app", "src", "main", "python")
    if os.path.isdir(py_dst): shutil.rmtree(py_dst)
    os.makedirs(py_dst)
    for d in ("math_universe_engine", "math_universe_linalg", "schema"):
        shutil.copytree(os.path.join(engine, d), os.path.join(py_dst, d), ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copy(os.path.join(app, "android_bridge", "mu_bridge.py"), py_dst)

    kt_dir = os.path.join(android, "app", "src", "main", "kotlin", "com", "mathuniverse", "math_universe_app")
    os.makedirs(kt_dir, exist_ok=True)
    shutil.copy(os.path.join(os.path.dirname(os.path.abspath(__file__)), "MainActivity.kt"), os.path.join(kt_dir, "MainActivity.kt"))
    for stale in (os.path.join(android, "app", "src", "main", "java"),):   # plantillas antiguas
        if os.path.isdir(stale): shutil.rmtree(stale, ignore_errors=True)

    # --- settings.gradle(.kts): declarar el plugin ---
    kts = os.path.exists(os.path.join(android, "settings.gradle.kts"))
    sp = os.path.join(android, "settings.gradle.kts" if kts else "settings.gradle")
    s = leer(sp)
    if "com.chaquo.python" not in s:
        decl = f'    id("com.chaquo.python") version "{CHAQUOPY}" apply false\n' if kts else f'    id "com.chaquo.python" version "{CHAQUOPY}" apply false\n'
        s2, n = re.subn(r"(plugins\s*\{\n)", lambda m: m.group(1) + decl, s, count=1)
        if n != 1: sys.exit("patch_android: no se encontro el bloque plugins{} en " + sp)
        escribir(sp, s2)

    # --- app/build.gradle(.kts): aplicar el plugin, ABIs y version de Python ---
    bp = os.path.join(android, "app", "build.gradle.kts" if kts else "build.gradle")
    b = leer(bp)
    if "com.chaquo.python" not in b:
        app_plugin = '    id("com.chaquo.python")\n' if kts else '    id "com.chaquo.python"\n'
        # Chaquopy debe aplicarse DESPUES del plugin de Android
        b, n = re.subn(r"([^\n]*com\.android\.application[^\n]*\n)", lambda m: m.group(1) + app_plugin, b, count=1)
        if n != 1: sys.exit("patch_android: no se encontro el plugin com.android.application en " + bp)
        abi = ('        ndk {\n            abiFilters += listOf("arm64-v8a", "x86_64")\n        }\n' if kts else
               '        ndk {\n            abiFilters "arm64-v8a", "x86_64"\n        }\n')
        b, n = re.subn(r"(defaultConfig\s*\{\n)", lambda m: m.group(1) + abi, b, count=1)
        if n != 1: sys.exit("patch_android: no se encontro defaultConfig{} en " + bp)
        # Chaquopy exige minSdk >= 24
        if kts:
            b, n = re.subn(r"minSdk\s*=\s*flutter\.minSdkVersion", "minSdk = maxOf(24, flutter.minSdkVersion)", b, count=1)
        else:
            b, n = re.subn(r"minSdk(Version)?\s+flutter\.minSdkVersion", "minSdkVersion Math.max(24, flutter.minSdkVersion)", b, count=1)
        if n != 1: sys.exit("patch_android: no se encontro minSdk = flutter.minSdkVersion en " + bp)
        if kts:
            pip = "".join(f'            install("{p}")\n' for p in PIP)
            b += (f'\nchaquopy {{\n    defaultConfig {{\n        version = "{PYVER}"\n        pip {{\n{pip}        }}\n    }}\n}}\n')
        else:
            pip = "".join(f'            install "{p}"\n' for p in PIP)
            b += (f'\nchaquopy {{\n    defaultConfig {{\n        version "{PYVER}"\n        pip {{\n{pip}        }}\n    }}\n}}\n')
        escribir(bp, b)
    print("Android preparado: motor Python (Chaquopy %s, Python %s, %s) integrado." % (CHAQUOPY, PYVER, ", ".join(PIP)))


if __name__ == "__main__":
    if len(sys.argv) != 3: sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
