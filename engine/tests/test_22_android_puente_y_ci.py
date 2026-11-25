"""Puente Android (sin Android), parche de Gradle sobre plantillas sinteticas y coherencia de los workflows de CI."""
import json, os, subprocess, sys
import pytest

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ENGINE = os.path.join(RAIZ, "engine")
PATCH = os.path.join(RAIZ, "tools", "ci", "patch_android.py")

KTS_SETTINGS = 'pluginManagement {\n    repositories { google() }\n}\n\nplugins {\n    id("dev.flutter.flutter-plugin-loader") version "1.0.0"\n    id("com.android.application") version "8.7.3" apply false\n}\n\ninclude(":app")\n'
KTS_APP = 'plugins {\n    id("com.android.application")\n    id("dev.flutter.flutter-gradle-plugin")\n}\n\nandroid {\n    defaultConfig {\n        applicationId = "x"\n        minSdk = flutter.minSdkVersion\n    }\n}\n'
GROOVY_SETTINGS = 'pluginManagement {\n}\nplugins {\n    id "dev.flutter.flutter-plugin-loader" version "1.0.0"\n    id "com.android.application" version "8.7.3" apply false\n}\ninclude ":app"\n'
GROOVY_APP = 'plugins {\n    id "com.android.application"\n    id "dev.flutter.flutter-gradle-plugin"\n}\nandroid {\n    defaultConfig {\n        applicationId "x"\n        minSdkVersion flutter.minSdkVersion\n    }\n}\n'


def _proyecto(tmp_path, kts):
    app = tmp_path / "app"
    (app / "android" / "app").mkdir(parents=True)
    (app / "android_bridge").mkdir()
    with open(os.path.join(RAIZ, "app", "android_bridge", "mu_bridge.py"), encoding="utf-8") as f: txt = f.read()
    (app / "android_bridge" / "mu_bridge.py").write_text(txt, encoding="utf-8")
    ext = ".kts" if kts else ""
    (app / "android" / f"settings.gradle{ext}").write_text(KTS_SETTINGS if kts else GROOVY_SETTINGS, encoding="utf-8")
    (app / "android" / "app" / f"build.gradle{ext}").write_text(KTS_APP if kts else GROOVY_APP, encoding="utf-8")
    return app


@pytest.mark.parametrize("kts", [True, False], ids=["kotlin-dsl", "groovy"])
def test_parche_android_y_es_idempotente(tmp_path, kts):
    app = _proyecto(tmp_path, kts)
    for _ in range(2):
        r = subprocess.run([sys.executable, PATCH, str(app), ENGINE], capture_output=True, text=True, encoding="utf-8", timeout=60)
        assert r.returncode == 0, r.stdout + r.stderr
    ext = ".kts" if kts else ""
    b = (app / "android" / "app" / f"build.gradle{ext}").read_text(encoding="utf-8")
    s = (app / "android" / f"settings.gradle{ext}").read_text(encoding="utf-8")
    assert b.count("com.chaquo.python") == 1 and s.count("com.chaquo.python") == 1 and b.count("chaquopy {") == 1
    assert b.index("com.android.application") < b.index("com.chaquo.python")         # Chaquopy despues del plugin de Android
    assert "sympy==1.14.0" in b and "mpmath==1.3.0" in b, "SymPy y mpmath deben empaquetarse dentro del APK"
    assert "24" in b.split("minSdk")[1].split("\n")[0], "Chaquopy exige minSdk >= 24"
    g = (app / "android" / "gradle.properties").read_text(encoding="utf-8")
    assert g.count("disable-abi-filtering=true") == 1, "Flutter no debe reponer armeabi-v7a (sin Python 3.12 en Chaquopy)"
    py = app / "android" / "app" / "src" / "main" / "python"
    assert {"math_universe_engine", "math_universe_linalg", "schema", "mu_bridge.py"} <= set(os.listdir(py))
    assert (app / "android" / "app" / "src" / "main" / "kotlin" / "com" / "mathuniverse" / "math_universe_app" / "MainActivity.kt").exists()


def test_parche_falla_con_mensaje_si_no_reconoce_el_formato(tmp_path):
    app = _proyecto(tmp_path, True)
    (app / "android" / "settings.gradle.kts").write_text("// vacio\n", encoding="utf-8")
    r = subprocess.run([sys.executable, PATCH, str(app), ENGINE], capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode != 0 and "plugins" in (r.stdout + r.stderr)


def test_puente_android_funciona_con_el_motor_copiado_y_sin_jsonschema(tmp_path):
    """Simula Android: solo los paquetes que copia el parche, sin jsonschema ni NumPy/SymPy, en modo aislado."""
    app = _proyecto(tmp_path, True)
    subprocess.run([sys.executable, PATCH, str(app), ENGINE], check=True, capture_output=True, timeout=60)
    py = str(app / "android" / "app" / "src" / "main" / "python")
    code = ("import sys, json; sys.path.insert(0, %r)\n"
            "import builtins; real = builtins.__import__\n"
            "def imp(n, *a, **k):\n"
            "    if n.split('.')[0] in ('jsonschema', 'numpy', 'scipy', 'sympy', 'mpmath'): raise ImportError(n)\n"
            "    return real(n, *a, **k)\n"
            "builtins.__import__ = imp\n"
            "import mu_bridge\n"
            "out = [json.loads(mu_bridge.handle(x)) for x in (\n"
            "  json.dumps({'operation': 'matrix_det', 'request_id': 1, 'structured_input': {'a': [[1, 2], [3, 4]]}}),\n"
            "  json.dumps({'operation': 'evaluate', 'request_id': 2, 'expression': '1/3+1/6'}),\n"
            "  json.dumps({'operation': 'matrix_inverse', 'request_id': 3, 'structured_input': {'a': [[1, 2], [2, 4]]}}),\n"
            "  'esto no es json')]\n"
            "print(json.dumps(out))\n") % py
    r = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    a, b, c, d = json.loads(r.stdout)
    assert a["exact_result"] == "-2" and a["verification"]["status"] == "passed"
    assert b["exact_result"] == "1/2"
    assert c["status"] == "domain_error" and c.get("exact_result") is None
    assert d["status"] == "internal_error"


def test_puente_android_funciona_importando_el_motor_desde_un_zip_sin_carpeta_schema(tmp_path):
    """Como en el APK (Chaquopy): el código se importa desde un ZIP y no hay archivos en disco. Reproduce el
    FileNotFoundError visto en el emulador (CI 2026-11-25) y comprueba la corrección."""
    import zipfile
    app = _proyecto(tmp_path, True)
    subprocess.run([sys.executable, PATCH, str(app), ENGINE], check=True, capture_output=True, timeout=60)
    py = app / "android" / "app" / "src" / "main" / "python"
    z = tmp_path / "app.zip"
    with zipfile.ZipFile(z, "w") as zf:
        for f in py.rglob("*"):
            rel = f.relative_to(py).as_posix()
            if f.is_file() and not rel.startswith("schema/") and "__pycache__" not in rel:
                zf.write(f, rel)
    code = ("import sys, json; sys.path.insert(0, %r)\n"
            "import mu_bridge\n"
            "print(json.dumps([json.loads(mu_bridge.handle(json.dumps(r))) for r in (\n"
            "  {'operation': 'ping', 'request_id': 1},\n"
            "  {'operation': 'evaluate', 'request_id': 2, 'expression': '1+1'},\n"
            "  {'operation': 'capabilities', 'request_id': 3})]))\n") % str(z)
    r = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, encoding="utf-8", timeout=120,
                       cwd=str(tmp_path))
    assert r.returncode == 0, r.stderr
    a, b, c = json.loads(r.stdout)
    assert a["status"] == "success_exact", a
    assert b["exact_result"] == "2", b
    assert c["status"] == "success_exact" and c["data"]["engine_version"] == "0.6.0", c


def _workflow():
    with open(os.path.join(RAIZ, ".github", "workflows", "construir.yml"), encoding="utf-8") as f: return f.read()


def test_workflow_ejecuta_pruebas_compila_verifica_y_publica():
    t = _workflow()
    for clave in ("pytest tests", "flutter analyze", "flutter test", "upload-artifact", "MATH_UNIVERSE_ENGINE_DIR",
                  "flutter build windows", "package_windows.ps1", "verify_windows_install.ps1",
                  "flutter build apk", "patch_android.py", "verify_android_install.sh", "android-emulator-runner",
                  "MATH_UNIVERSE_SETUP.exe", "MATH_UNIVERSE.apk", "gh release create"):
        assert clave in t, clave
    assert "continue-on-error" not in t, "ninguna comprobacion debe poder fallar en silencio"
    assert "needs: [windows, android, android_instalado_sin_red]" in t, "solo se publica lo verificado en ambas plataformas"
    assert "sympy==1.14.0" in t and "mpmath==1.3.0" in t, "mismas versiones que las empaquetadas"


def test_windows_no_usa_actions_checkout():
    """El nombre del repositorio termina en punto: actions/checkout falla en Windows (CI 2026-11-25)."""
    t = _workflow()
    windows = t.split("\n  android:")[0]
    assert "uses: actions/checkout" not in windows and "git checkout -q FETCH_HEAD" in windows


def test_verificacion_instalada_sin_red():
    with open(os.path.join(RAIZ, "tools", "ci", "verify_windows_install.ps1"), encoding="utf-8") as f: w = f.read()
    for clave in ("/VERYSILENT", "New-NetFirewallRule", "--autotest=", "todo_correcto", "HAY RED"):
        assert clave in w, clave
    with open(os.path.join(RAIZ, "tools", "ci", "verify_android_install.sh"), encoding="utf-8") as f: a = f.read()
    for clave in ("airplane-mode enable", "ping -c 1", "--ez autotest true", "MU_AUTOTEST_FIN", '"todo_correcto":true'):
        assert clave in a, clave


def test_el_paquete_windows_incluye_todo_lo_necesario():
    with open(os.path.join(RAIZ, "tools", "ci", "package_windows.ps1"), encoding="utf-8") as f: t = f.read()
    for clave in ("python-$PyVer-embed-amd64.zip", "jsonschema", "sympy==1.14.0", "mpmath==1.3.0", "run_server.py", "ISCC",
                  "matrix_det", "1e999999999", "sympy_respaldo_experimental", "vcruntime140.dll", "SHA256"):
        assert clave in t, clave
    with open(os.path.join(RAIZ, "installer", "MathUniverse.iss"), encoding="utf-8") as f: iss = f.read()
    assert "PrivilegesRequired=lowest" in iss and "runner\\Release" in iss and "OutputBaseFilename=MATH_UNIVERSE_SETUP" in iss
