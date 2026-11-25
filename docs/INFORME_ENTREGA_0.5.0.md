# Informe de entrega · MATH UNIVERSE 0.5.0

Fecha: 2026-11-25. Compilación verificada: GitHub Actions, ejecución **45544750785** (commit `8ec3441`), las 4 tareas en verde.
Release: <https://github.com/ll202001-ai/math-universe./releases/tag/v0.5.0>

## Estado
| Plataforma | Estado | Evidencia |
|---|---|---|
| **Windows** | Instalador `MATH_UNIVERSE_SETUP.exe` (≈29 MB) compilado, instalado y verificado **sin red** | Instalación silenciosa, accesos directos (menú Inicio y escritorio), firewall bloqueando la app y su Python (comprobado: `URLError`), autoprueba de la app instalada **17/17**, arranque normal con su motor `pythonw.exe`, desinstalación correcta |
| **Android** | `MATH_UNIVERSE.apk` (≈94 MB, arm64-v8a + x86_64) compilado, instalado y verificado **en modo avión** | Emulador Android 14: APK de release instalado, sin red (comprobado con ping), autoprueba **17/17**, arranque normal sin errores fatales |

## Pruebas
| Grupo | Resultado |
|---|---|
| Motor (pytest) en Windows y Linux, con SymPy 1.14.0 y mpmath 1.3.0 reales | **858 aprobadas, 0 falladas, 0 omitidas** en ambas plataformas |
| Flutter: análisis estático | sin errores ni advertencias (solo avisos informativos de estilo) |
| Flutter: pruebas (unidad, interfaz, cliente Dart ↔ motor Python real, autoprueba con SQLite real, migración del historial) | **26/26** en Windows y Linux |
| Motor empaquetado de Windows (Python embebido aislado) | 7/7 (incluye SymPy y mpmath) |
| Autoprueba de la app **instalada y sin red** | Windows 17/17 · Android 17/17 |

Autoprueba (idéntica en ambas plataformas, ejecutada por la propia app; informes `AUTOPRUEBA_WINDOWS.json` y `AUTOPRUEBA_ANDROID.txt` en la release):
motor responde · SymPy y mpmath presentes · `1+1 = 2` · `1/3+1/6 = 1/2` · factorizar `x^2-5*x+6` (verificado por re-expansión) ·
expandir `(x-2)*(x-3)` · resolver `x^2-5*x+6=0` (raíces sustituidas) · sistema `2x+y=5; x-y=1` · despejar `R` en `V=I*R` con `I ≠ 0` ·
derivar `x^3*sin(x)` (contraste numérico) · integrar `x^2` con `+ C` (verificado derivando) · `lim sin(x)/x = 1` ·
`(x^3-8)/(x-2)` conserva `x ≠ 2` · SymPy real: `∫sin(x)^2` · `det [[1,2],[3,4]] = -2` · inversa con `A·A⁻¹ = I` ·
historial SQLite: guardar, cerrar, reabrir, recuperar.

## Funcionamiento sin conexión
- **Comprobado** en Windows Server (GitHub) con el firewall bloqueando la app y su Python, y en un emulador Android 14 en modo avión.
- **Pendiente:** prueba en un PC y en un teléfono físicos. La app incluye «Comprobar instalación» (menú ⋮), que ejecuta la misma autoprueba en su equipo.

## Errores encontrados y corregidos en esta entrega
Detalle en `REGISTRO_ERRORES.md` (CI-1 a CI-5, F-1 a F-3) y decisiones en `DECISIONES.md` (ADR-4 a ADR-10). Además, la
autoprueba en el emulador detectó dos defectos que solo existían dentro del APK: los esquemas JSON no se podían leer desde el ZIP
de Chaquopy, y el respaldo SymPy usaba procesos hijo, que Android no permite. Ambos se corrigieron con pruebas que los reproducen
(`test_22`, `test_24`).

## Versión
Producto 0.5.0 · motor 0.5.0 · contrato 1.1 · Flutter 3.50.1 · Python 3.12 · SymPy 1.14.0 · mpmath 1.3.0 · Chaquopy 17.2.0.

## Limitaciones
Ver `LIMITACIONES.md`. Lo principal: no hay todavía gráficas, estadística, autovalores, EDO, ingeniería eléctrica ni entrada
manuscrita o en lenguaje natural; no se muestra un procedimiento paso a paso (solo método y verificación); instalador y APK sin
firma comercial (aviso de SmartScreen / Play Protect); Android solo de 64 bits.
