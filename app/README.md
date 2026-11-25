# MATH UNIVERSE · cliente Flutter (Windows y Android)

Interfaz de MATH UNIVERSE. Todo cálculo lo hace el motor Python local (`../engine`), al que se llega por:
- **Windows:** proceso hijo con Python embebido (JSON Lines por stdin/stdout), ver `lib/engine/engine_client.dart`.
- **Android:** Chaquopy dentro del APK y un `MethodChannel` (`tools/ci/MainActivity.kt`, `android_bridge/mu_bridge.py`).

Pruebas: `flutter test` (con `MATH_UNIVERSE_ENGINE_DIR=../engine` se ejecutan también las pruebas con el motor real).
La compilación de los instaladores la hace GitHub Actions (`.github/workflows/construir.yml`).
