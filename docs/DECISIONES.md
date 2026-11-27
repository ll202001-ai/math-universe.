# Registro de decisiones técnicas (ADR) · versión 0.6.0

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

## ADR-11 · Módulos avanzados con SymPy, siempre con verificación independiente (0.6.0)
- **Problema:** la 0.5.0 era «muy básica» (solo el motor exacto propio). Reescribir un CAS completo no es razonable.
- **Decisión:** SymPy calcula autovalores, EDO, transformadas, series, etc.; cada resultado se comprueba por una vía
  distinta (A·v = λ·v exacto, diferencias finitas mpmath, `checkodesol`, cuadratura numérica de mpmath, módulo
  `statistics`, `cmath`, reconversión de unidades). Si la comprobación falla, el resultado no se entrega. Las pruebas
  usan valores conocidos a mano e incluyen verificaciones saboteadas.
- **Contrato 1.2 (aditivo):** operaciones nuevas, `params`, `conditions`, `latex`, `steps`.

## ADR-12 · Presentación matemática con LaTeX generado por el motor
- El motor genera LaTeX con SymPy **sin evaluar** (lo que se dibuja es exactamente lo calculado; `sqrt(x)^2` no se
  convierte en `x`). La app lo dibuja con `flutter_math_fork` (Dart puro, sin WebView, funciona sin red) y, si falla,
  muestra el texto. Alternativa descartada: `flutter_tex` (WebView, peor rendimiento y depende del motor web).

## ADR-13 · Gráficas: el motor muestrea, la app dibuja
- El muestreo usa el mismo AST seguro (sin `eval`), corta la curva en asíntotas y puntos no definidos, y marca ceros
  (bisección) y extremos. La app usa un `CustomPainter` propio (zoom, desplazamiento, remuestreo al cambiar la vista,
  3D con giro). Se descartó `fl_chart`: no permite remuestrear la vista ni cortar asíntotas con control fino.

## ADR-14 · Lenguaje natural por reglas, no por IA (por ahora)
- «deriva x al cubo por seno de x» → operación + expresión; la app muestra «Entendí: …» y solo calcula al confirmar.
  Una IA en línea requeriría proveedor, clave y consentimiento de envío de datos; queda como servicio opcional futuro.

## ADR-15 · Editor matemático estructurado nativo en Flutter (0.7.0)
- La entrada pasa a ser un árbol (`app/lib/editor/math_node.dart`): filas de nodos con ranuras editables (fracción
  numerador/denominador, potencia, subíndice, raíz e índice, |x|, ⌊x⌋, ⌈x⌉, funciones, log en base b, integral con
  límites, Σ, Π, límite, d/dx, matrices m×n y sistemas). Un cursor (ruta dentro del árbol) se mueve con ← → ↑ ↓ y Tab
  (siguiente casilla vacía); deshacer/rehacer con instantáneas (máx. 200).
- Se dibuja con `flutter_math_fork` (LaTeX con `\square` en casillas vacías y una barra de cursor coloreada) y se
  serializa al texto del contrato del motor (`toEngine`). Las plantillas de cálculo del nivel superior (integral, Σ, Π,
  lím, d/dx, matriz, sistema) se convierten en la OPERACIÓN y parámetros correspondientes del contrato (`toRequest`).
- **Alternativa descartada: MathLive en un WebView.** Requiere WebView2 en Windows y otro WebView en Android, dos pilas de
  interfaz, un puente JavaScript y no se puede probar con las pruebas de widgets de Flutter. El editor nativo funciona
  igual en ambas plataformas, sin red, y cada botón tiene prueba automática.
- Lo que no se puede enviar al motor no se simula: una casilla vacía o una integral/Σ anidada dentro de otra expresión
  muestran un mensaje claro («Complete el denominador…», «La integral debe ser la expresión completa…»).
- Teclado de 10 pestañas (`keyboard_layout.dart`): Básico, Álgebra, Cálculo, Trigonometría, Matrices y vectores,
  Estadística, Ecuaciones, Griegas, Lógica y conjuntos, Funciones especiales; fila fija de control (← → ↑ ↓, siguiente,
  deshacer, rehacer, borrar, AC) y de acciones (Simplificar, Expandir, Factorizar, Resolver, =).
- Teclado físico: `/` convierte el término anterior en numerador, `^` exponente, `_` subíndice, `|` valor absoluto,
  palabras (`sin`, `sqrt`, `pi`, `alpha`…) se convierten en función/símbolo; Ctrl+Z/Y, Ctrl+C/V, Enter = calcular.
- Hoja de trabajo: varias expresiones en bloques con su resultado; tocar un bloque lo reabre para editarlo y recalcular.
  La línea de texto sigue disponible y se sincroniza en ambos sentidos con el editor (pegar texto → estructura).

## ADR-16 · Motor 0.7.0 (contrato 1.3, aditivo)
- Nuevas operaciones en `advanced2.py`, todas con SymPy y una comprobación independiente: `sum`/`product` (suma
  directa de términos o sumas parciales con mpmath para series), `substitute` (evaluador propio en puntos),
  `matrix_symbolic` (A·A⁻¹ = I simplificado, det por dos métodos, evaluación en puntos racionales), `logic` (tabla de
  verdad completa con un parser propio), `sets` (pertenencia en puntos de prueba) e `implicit_diff`.
- Funciones nuevas: `%`, `log(x,b)`, `cbrt`, `root`, sec/csc/cot, asinh/acosh/atanh, gamma, erf, erfc, beta, zeta,
  besselj, floor, ceil. `evaluate` tiene respaldo SymPy verificado; un resultado `zoo`/`nan` es error de dominio, nunca un
  «resultado».
