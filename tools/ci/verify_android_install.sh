#!/usr/bin/env bash
# Verificacion REAL del APK de release en un emulador Android (GitHub Actions):
#  1. instala MATH_UNIVERSE.apk (el mismo archivo que se publica);
#  2. activa el MODO AVION y comprueba que no hay red;
#  3. abre la app instalada en modo autoprueba (extra "autotest"): calculos reales en el motor Python empaquetado
#     (Chaquopy), SymPy, mpmath e historial SQLite (escribir, cerrar, reabrir, leer). Resultado leido de logcat;
#  4. reinicia la app normalmente y comprueba que sigue abierta sin errores fatales;
#  5. guarda el informe, el logcat y una captura de pantalla.
# Limite honesto: es un emulador x86_64, no un telefono fisico (arm64).
set -euo pipefail
APK="${1:?uso: verify_android_install.sh <apk> <carpeta de salida>}"
OUT="${2:?}"
PKG="com.mathuniverse.math_universe_app"
mkdir -p "$OUT"

adb wait-for-device
adb shell 'while [ "$(getprop sys.boot_completed)" != "1" ]; do sleep 2; done'
adb install -r "$APK"
echo "APK instalado: $(adb shell pm path $PKG)"

# 2) sin red
adb shell cmd connectivity airplane-mode enable || adb shell settings put global airplane_mode_on 1
adb shell svc wifi disable || true
adb shell svc data disable || true
sleep 5
if adb shell ping -c 1 -W 3 8.8.8.8 >/dev/null 2>&1; then
  echo "ERROR: el emulador todavia tiene red; la prueba sin conexion no seria valida"; exit 1
fi
echo "Modo avion activo: sin red (comprobado con ping)."

# 3) autoprueba de la app instalada
adb logcat -c
adb shell am start -W -n "$PKG/.MainActivity" --ez autotest true
FIN=""
for i in $(seq 1 120); do
  if adb logcat -d -s flutter:I | grep -q "MU_AUTOTEST_FIN"; then FIN=1; break; fi
  if adb logcat -d | grep -q "FATAL EXCEPTION"; then break; fi
  sleep 5
done
adb logcat -d > "$OUT/logcat_autoprueba.txt"
adb exec-out screencap -p > "$OUT/captura_autoprueba.png" || true
grep -E "MU_AUTOTEST" "$OUT/logcat_autoprueba.txt" | sed -E 's/^.*(MU_AUTOTEST[_A-Z]*) /\1 /' > "$OUT/AUTOPRUEBA_ANDROID.txt" || true
cat "$OUT/AUTOPRUEBA_ANDROID.txt"
if [ -z "$FIN" ]; then
  echo "ERROR: la autoprueba no termino (ver logcat_autoprueba.txt)"
  grep -E "FATAL|AndroidRuntime|chaquopy|python" "$OUT/logcat_autoprueba.txt" | tail -40 || true
  exit 1
fi
if ! grep "MU_AUTOTEST_FIN" "$OUT/AUTOPRUEBA_ANDROID.txt" | grep -q '"todo_correcto":true'; then
  echo "ERROR: la autoprueba de la app instalada tiene fallos"; exit 1
fi
echo "Autoprueba Android: todo correcto sin red."

# 4) arranque normal
adb shell am force-stop "$PKG"
adb logcat -c
adb shell am start -W -n "$PKG/.MainActivity"
sleep 25
adb logcat -d > "$OUT/logcat_arranque_normal.txt"
adb exec-out screencap -p > "$OUT/captura_arranque_normal.png" || true
if ! adb shell pidof "$PKG" >/dev/null; then echo "ERROR: la app se cerro al arrancar"; exit 1; fi
if grep -q "FATAL EXCEPTION" "$OUT/logcat_arranque_normal.txt"; then echo "ERROR: excepcion fatal al arrancar"; exit 1; fi
echo "Arranque normal sin red: la app sigue abierta y sin errores fatales."
adb shell cmd connectivity airplane-mode disable || true
