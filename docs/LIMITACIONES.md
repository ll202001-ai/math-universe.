# Limitaciones conocidas · MATH UNIVERSE 0.6.0

Lo que la versión 0.6.0 **no** hace todavía o hace con restricciones. Nada de esta lista se presenta en la app como
disponible. El catálogo exacto de operaciones no soportadas (generado y comprobado por las pruebas) está en
`NO_SOPORTADO.md`.

## Funciones de la especificación aún no implementadas (planificadas)
- Ecuaciones en derivadas parciales, elementos finitos, simulador de circuitos por análisis nodal, transformada de
  Fourier, integrales múltiples, regresión e inferencia estadística (intervalos, pruebas de hipótesis), cuaderno y
  proyectos, exportación a PDF.
- Entrada manuscrita (OCR) o por imagen y asistente de IA en línea (requiere un proveedor y su clave; se diseñará como
  servicio opcional). Las instrucciones en español se interpretan con reglas y SIEMPRE se piden confirmar.
- Editor visual 2D (cursor dentro de fracciones y exponentes): la entrada es texto + teclado científico, con vista previa
  dibujada de la fórmula.
- Paso a paso: solo ecuaciones de primer y segundo grado, derivadas y Gauss-Jordan (inversa y sistemas). En lo demás
  se muestran el método y la verificación independiente (no se inventan pasos).

## Disponible desde 0.6.0 (con verificación independiente)
Autovalores y autovectores (hasta 6×6), derivadas parciales, gradiente, Hessiano y Jacobiano, series de Taylor,
inecuaciones de una variable, números complejos (binómica y polar), EDO (SymPy dsolve), transformada de Laplace
directa e inversa, estadística descriptiva, unidades SI con análisis dimensional, biblioteca de fórmulas eléctricas,
gráficas 2D/paramétricas/polares/3D, LaTeX de entrada y resultado.

## Restricciones del motor
- Ecuaciones con radicales, valor absoluto, exponenciales, logaritmos o trigonométricas; cúbicas irreducibles; sistemas
  no lineales: devuelven «No soportado».
- Integrales: polinomios, racionales con factores lineales/cuadráticos, polinomio·{exp, sin, cos}, xᵏ·ln x; otras pasan
  a SymPy (respaldo, marcado como tal y verificado) y, si tampoco, «No soportado». Integrales impropias: no.
- Límites: series de Laurent; sin infinitos de funciones trascendentes.
- Matrices: solo entradas numéricas exactas (enteros, fracciones, decimales), hasta 40×40; sin matrices simbólicas.
- Supuestos (`real`, `positive`…) solo se aplican en simplificar/expandir/factorizar/resolver.
- Gráficas: ceros y extremos marcados son aproximaciones numéricas del muestreo.
- EDO y transformadas: si SymPy no encuentra solución cerrada se responde «No soportado» (todavía no hay solución numérica de EDO).
- Cifras arbitrarias (mpmath) solo para expresiones sin variables; si el contraste independiente no cuadra, se dan
  ~15 cifras con aviso.

## Plataformas y distribución
- **Probado automáticamente en:** Windows Server de GitHub (instalación real del `.exe`, sin red mediante firewall) y
  un emulador Android 14 x86_64 (instalación real del APK, modo avión). **No probado en un PC ni en un teléfono físicos**:
  la primera prueba en su equipo es la verificación definitiva (menú ⋮ → Comprobar instalación).
- Android: solo 64 bits (arm64-v8a, x86_64), Android 7.0 (API 24) o superior. Tamaño mayor que una app típica porque
  incluye CPython, SymPy y mpmath.
- Windows: solo x64. El instalador no está firmado con un certificado de firma de código: SmartScreen muestra un aviso.
- El APK está firmado con la clave de depuración de Flutter (instalable directamente; no apto para Google Play).
  Para publicar en Play Store hará falta una clave de firma propia.
- Cancelación en Android: si una operación agota el tiempo, se informa «Tiempo agotado», pero el hilo de Python puede
  seguir ocupado hasta terminar (en Windows el proceso del motor se reinicia).
- El historial se guarda localmente; todavía no hay favoritos, exportación ni sincronización.
- Tema y tamaño de texto se ajustan en el menú, pero no se recuerdan entre sesiones.
