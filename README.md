# MATH UNIVERSE · versión 0.5.0 (motor 0.5.0 · contrato 1.1)

Calculadora matemática exacta para Windows y Android. Funciona sin internet: el motor matemático (Python con SymPy y
mpmath) va dentro de la aplicación. **Para instalarla, lea [`LEEME_PRIMERO.md`](LEEME_PRIMERO.md).**

| Carpeta | Contenido |
|---|---|
| `app/` | Interfaz Flutter (Windows y Android): calculadora, teclado científico, matrices, historial SQLite, autoprueba |
| `engine/` | Motor Python: parser seguro, CAS exacto propio, respaldo SymPy, mpmath, álgebra lineal, verificación independiente, pruebas |
| `installer/` | Instalador de Windows (Inno Setup) |
| `tools/ci/` | Empaquetado de Windows, integración Android (Chaquopy) y verificación de la instalación sin red |
| `.github/workflows/construir.yml` | Compilación, pruebas, verificación y publicación automáticas |
| `docs/` | Informe de entrega (`INFORME_ENTREGA_0.5.0.md`), limitaciones (`LIMITACIONES.md`), decisiones técnicas (`DECISIONES.md`), contrato del motor |
| `versiones_anteriores/` | Fase 8, fase 9B y el ZIP de la fase 10, intactos y con sus hashes |

## Arquitectura (corrección arquitectónica rectora)
Flutter (Windows + Android) → contrato JSON 1.1 → motor Python local (SymPy + mpmath) · historial SQLite local.
- **Windows:** Python 3.12 embebido junto a la app; proceso hijo con JSON Lines por stdin/stdout.
- **Android:** CPython 3.12 dentro del APK (Chaquopy 17.2); `MethodChannel` → `mu_bridge.py`.

## Compilar y probar
Cada `push` ejecuta `.github/workflows/construir.yml`: pruebas del motor (Windows y Linux), análisis y pruebas Flutter,
compilación, empaquetado, **instalación real sin red** (Windows con el firewall bloqueando la app; Android en un emulador
en modo avión) y, solo si todo pasa, publicación en GitHub Releases.

Localmente: `cd engine && python -m pytest tests` · `cd app && MATH_UNIVERSE_ENGINE_DIR=../engine flutter test`.
