# Registro de decisiones técnicas (ADR) · versión 0.5.0

Las ADR-1 a ADR-3 están en `CONTRATO.md` (motor propio + respaldo SymPy verificado, dominio real por defecto, `log` = `ln`).

## ADR-4 · El código fuente vive en el repositorio (no en un ZIP)
- **Contexto:** hasta la fase 10 el repositorio solo contenía un ZIP que el CI descomprimía. Cada corrección exigía un ZIP nuevo.
- **Decisión:** el contenido de `MATH_UNIVERSE_fase10.zip` se versiona directamente. El ZIP se conserva intacto en
  `versiones_anteriores/fase10/` con su SHA-256 en `versiones_anteriores/HASHES_ZIP.txt` (lo comprueba `test_20`).
- **Consecuencia:** cambios pequeños, revisables y trazables en Git. El flujo «subir un ZIP» queda retirado.

## ADR-5 · Windows sin `actions/checkout`
- **Evidencia:** run 45532010131 → `Directory 'D:\a\math-universe.\math-universe.' does not exist`. Un diagnóstico
  (run 45536990741) mostró que el runner crea `D:\a\math-universe\math-universe` (Windows elimina el punto final) y
  que los pasos `run`, `setup-python` y `upload-artifact` funcionan. Solo `actions/checkout` falla.
- **Decisión:** en Windows el código se obtiene con `git fetch` del commit exacto. Alternativa descartada: renombrar el
  repositorio (habría requerido una acción del propietario y cambiaría su URL).

## ADR-6 · Plataforma Android: Chaquopy 17.2.0, Python 3.12, SymPy y mpmath en el APK
- **Evidencia:** Flutter 3.50.1 genera Android Gradle Plugin 9.3.1 y Gradle 9.5. Chaquopy 16.0.0 (fase 10) es anterior;
  el plugin 17.2.0 (Maven Central) declara AGP ≥ 7.3, minSdk ≥ 24 y Python 3.10–3.15.
- **Decisión:** Chaquopy 17.2.0; `minSdk = max(24, flutter.minSdkVersion)`; ABIs arm64-v8a (teléfonos) y x86_64
  (emuladores); `pip install sympy==1.14.0 mpmath==1.3.0` en tiempo de compilación (no de ejecución).
- **Consecuencia:** Android 7.0+ de 64 bits. Los teléfonos de 32 bits no están soportados.

## ADR-7 · Windows: Python 3.12 embebido + SymPy + mpmath + runtime VC++ dentro del instalador
- Python oficial «embeddable» de python.org; `._pth` restringe el `sys.path` a la carpeta de la app; se lanza con `-I`
  (aislado) y con `pythonw.exe` (sin ventana de consola). Se copian `msvcp140.dll`, `vcruntime140.dll` y
  `vcruntime140_1.dll` junto al ejecutable (despliegue local permitido por Microsoft) para que abra en un Windows limpio.
- Mismas versiones que Android (`engine/requirements-lock.txt`).

## ADR-8 · SQLite: `sqflite` (Android) y `sqflite_common_ffi` + `package:sqlite3` 3.x (Windows)
- `sqlite3_flutter_libs` está marcado como «fin de vida» (0.6.0+eol); `package:sqlite3` 3.x empaqueta SQLite con
  *build hooks*. Se elimina la dependencia obsoleta. Cada apertura del historial es una conexión propia
  (`singleInstance: false`) para que la autoprueba pueda cerrar y reabrir sin cerrar la conexión de la app.

## ADR-9 · Verificación de la app INSTALADA y sin red como condición de publicación
- La app tiene un modo de autoprueba (`--autotest=<informe.json>` en Windows; extra de intent `autotest` en Android) que
  ejecuta las pruebas de aceptación en el motor empaquetado, SymPy, mpmath y SQLite (escribir, cerrar, reabrir, leer).
  El mismo código está disponible para el usuario en «Comprobar instalación».
- CI: Windows instala el `.exe` en silencio y bloquea con el firewall la red de la app y de su Python (y comprueba que
  el bloqueo funciona); Android instala el APK de release en un emulador en modo avión (y comprueba que no hay red).
- El trabajo `publicar` depende de ambas verificaciones: nada sin verificar llega a Releases.

## ADR-10 · mpmath para cifras arbitrarias
- Solo se usa si se piden más de 15 cifras para un resultado no racional. El valor se contrasta con la evaluación en
  coma flotante (`math`), que es independiente. Si no coinciden, no se entrega y se avisa.
