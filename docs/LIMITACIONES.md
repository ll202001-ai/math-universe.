# Limitaciones conocidas · MATH UNIVERSE 0.5.0

Lo que la versión 0.5.0 **no** hace todavía o hace con restricciones. Nada de esta lista se presenta en la app como
disponible. El catálogo exacto de operaciones no soportadas (generado y comprobado por las pruebas) está en
`NO_SOPORTADO.md`.

## Funciones de la especificación aún no implementadas (planificadas)
- Gráficas 2D/3D, estadística y probabilidad, autovalores/autovectores y descomposiciones (LU, QR, SVD), ecuaciones
  diferenciales, series de Fourier y transformadas, números complejos como módulo propio, unidades y análisis
  dimensional, métodos numéricos configurables, ingeniería eléctrica, física, cuaderno/proyectos y exportación a PDF.
- Entrada manuscrita (OCR), por imagen, por voz y en lenguaje natural libre. El editor es de texto con teclado científico
  (no un editor visual 2D de fracciones y exponentes).
- Procedimiento paso a paso: la app muestra el método aplicado, la interpretación, las restricciones y la verificación
  independiente, pero no una secuencia de transformaciones (no se inventan pasos).

## Restricciones del motor
- Ecuaciones con radicales, valor absoluto, exponenciales, logaritmos o trigonométricas; cúbicas irreducibles; sistemas
  no lineales: devuelven «No soportado».
- Integrales: polinomios, racionales con factores lineales/cuadráticos, polinomio·{exp, sin, cos}, xᵏ·ln x; otras pasan
  a SymPy (respaldo, marcado como tal y verificado) y, si tampoco, «No soportado». Integrales impropias: no.
- Límites: series de Laurent; sin infinitos de funciones trascendentes.
- Matrices: solo entradas numéricas exactas (enteros, fracciones, decimales), hasta 40×40; sin matrices simbólicas.
- Supuestos (`real`, `positive`…) solo se aplican en simplificar/expandir/factorizar/resolver.
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
