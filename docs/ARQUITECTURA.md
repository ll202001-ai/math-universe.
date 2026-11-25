# MATH UNIVERSE · Fase 1: arquitectura, versiones, riesgos y plan de pruebas

Estado (actualizado en la etapa 2: ver CONTRATO.md y FUNCIONES.md para el estado vigente del motor): **documento + motor verificado**. La app Flutter, el APK y el instalador de Windows **aún no existen** (ver §8).

## 1. Diagrama

```
                 ┌────────────────────────────── Flutter / Dart (UI única) ──────────────────────────────┐
                 │  Barra universal · teclado · resultados · pasos · gráficas · historial (SQLite/drift)  │
                 └───────────────┬──────────────────────────────────────────────┬────────────────────────┘
                                 │ abstracción EngineClient (misma API JSON)    │
              ┌──────────────────▼───────────────┐              ┌───────────────▼────────────────────┐
              │ ANDROID: MethodChannel → plugin  │              │ WINDOWS: Process.start (local)     │
              │ Kotlin → Chaquopy (CPython en    │              │ python embebido + math_universe_   │
              │ el mismo proceso, hilo aparte)   │              │ engine.server  (JSON Lines stdin/  │
              │ cancelar = hilo/proceso worker   │              │ stdout). cancelar = kill + relanzar│
              └──────────────────┬───────────────┘              └───────────────┬────────────────────┘
                                 └───────────────┬──────────────────────────────┘
                              ┌──────────────────▼───────────────────┐
                              │ math_universe_engine (Python puro)   │
                              │ schema → dispatcher → parser seguro  │
                              │ → arith exacta │ symbolic (SymPy)    │
                              │ → (futuro) mpmath, numpy/scipy opc.  │
                              └──────────────────────────────────────┘
```
Un solo código del motor en ambas plataformas. Sin sockets ni servidores: en Windows el canal es stdin/stdout de un proceso hijo; en Android, llamadas en proceso.

## 2. Versiones (a fijar tras verificación; no confirmadas en este entorno)
| Pieza | Dato encontrado | Acción |
|---|---|---|
| Flutter | 3.47 estable (ago 2026); 3.50 planificada para nov 2026, no confirmada como publicada | Fijar la última estable con `flutter --version` y registrar el Dart que trae |
| Chaquopy | 17.0.0 (fuente secundaria), AGP 7.3–9.1 | Confirmar en la documentación oficial y en la tabla Python↔API mínima |
| Python | Aquí hay 3.13; Chaquopy y sus wheels pueden ir por detrás | **Elegir la versión que Chaquopy soporte con sus wheels**, y usar la misma en Windows |
| SymPy, mpmath | Python puro: sin problemas de ABI | Fijar versiones en `requirements.lock` |
| NumPy/SciPy | Chaquopy tiene repositorio propio de wheels; un informe de issue indica SciPy solo para Python 3.8–3.10 (puede estar desfasado) | **Opcionales**; verificar antes de depender de ellos en Android |

## 3. Protocolo (alineado con la Corrección arquitectónica rectora, §7)
Solicitud: `request_id, operation, expression, structured_input, variables, assumptions, precision, timeout_ms, engine_version`. Respuesta: `request_id, status, parsed_input, exact_result, approximate_result, conditions, warnings, method, verification, elapsed_ms`. Estados: `success_exact, success_approximate, unsupported, invalid_input, domain_error, no_solution, multiple_solutions, timeout, cancelled, internal_error`.
Pendiente: `timeout_ms` y la cancelación los aplicará el anfitrión (matar y relanzar el proceso); el motor aún no los hace cumplir por sí mismo. `assumptions` se valida en el esquema pero aún no se usa.
Esquemas validados con JSON Schema: `engine/schema/request.schema.json` y `response.schema.json` (campos extra rechazados). Códigos de error: `INVALID_REQUEST, PARSE_ERROR, DOMAIN_ERROR, NOT_IMPLEMENTED, DEPENDENCY_MISSING, LIMIT_EXCEEDED, NOT_SOLVED, INTERNAL_ERROR`. `result_kind` distingue exacto / aproximación / no encontrado / no implementado, sin confundir "no sé resolverlo" con "no tiene solución".

## 4. Empaquetado
- Android: Chaquopy empaqueta CPython + paquetes pip en el APK/AAB; ABIs `arm64-v8a` (+ `x86_64` solo para emulador).
- Windows: Python embebible (zip) + `site-packages` pre-instalados dentro de la carpeta de la app; instalador MSIX o Inno Setup. El usuario no instala Python.
- Ejecución con `python -I` (modo aislado) para no cargar código del directorio actual ni variables de entorno.

## 5. Tamaño estimado (orden de magnitud, sin medir)
Solo SymPy+mpmath: APK ≈ 40–70 MB por ABI; Windows ≈ 120–200 MB instalado. Con NumPy/SciPy sube bastante. Cifras reales se medirán al construir.

## 6. Riesgos
1. Versión de Python vs wheels de Chaquopy (afecta a NumPy/SciPy). Mitigación: núcleo solo SymPy/mpmath.
2. SymPy puede tardar o agotar memoria con integrales/ecuaciones difíciles. Mitigación: ejecutar en worker cancelable con límites y *timeout*.
3. Cancelación en Android (hilo Python no se mata limpiamente): usar proceso/worker aislable o límites cooperativos.
4. Pasos detallados: SymPy no da procedimientos completos; hay que escribirlos propios por módulo, o declarar que no hay pasos.
5. Gráficas 3D en Flutter offline: evaluar paquetes sin red; el muestreo se hace en Python.
6. Alcance del catálogo (17 módulos): se entrega por fases con estado honesto por módulo.
7. Firma del APK / SmartScreen en Windows sin certificado de firma.

## 7. Plan de pruebas
- Motor: `pytest` (aquí: 40 pasan, 2 omitidas). Pruebas con valores conocidos y comprobación inversa (derivar ↔ integrar, sustituir solución en la ecuación).
- Seguridad: entradas de inyección, límites de tamaño/profundidad/exponentes, JSON malformado.
- Protocolo: validación de esquema y pruebas del proceso JSON Lines.
- Integración: Windows (proceso real) y Android (emulador + dispositivo) por separado.
- Offline: instalación y uso con Wi-Fi y datos desactivados.

## 8. Estado real de módulos (motor 0.4.0, API 1.1)
| Módulo | Estado |
|---|---|
| Parser seguro (con cota de exponente, H-1) | Implementado y probado (Linux y Windows) |
| Aritmética exacta, simplificación con dominio, expansión, factorización, ecuaciones, sistemas, derivadas | Implementado y probado |
| Integrales y límites | Experimental (ver NO_SOPORTADO.md) |
| Álgebra lineal exacta (9 operaciones, verificación independiente) | Integrado en 0.4.0; 9B validado en Windows; la integración se probó en Linux |
| Respaldo SymPy y comparador motor↔SymPy | Probado en Windows con SymPy real hasta la fase 8; el código nuevo de comparación sigue pendiente de ejecución en Windows |
| Cliente Flutter (Windows), historial SQLite, instalador, Android | **Código escrito, NO compilado ni ejecutado** (ver `app/` y el informe de la entrega): la compilación se hace en GitHub Actions |
| Autovalores, estadística, ingeniería eléctrica, gráficas | No implementado |

## 9. Fase 0 (viabilidad vertical): estado
Flutter inicia · app invoca el motor local · modo avión tras instalación limpia · medidas de tamaño/latencia: **pendientes de la primera compilación en GitHub Actions y de una prueba en el equipo del usuario**. El servidor JSON Lines sí está probado con un subproceso (Linux y Windows).
