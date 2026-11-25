# Cómo obtener MATH UNIVERSE (instalador de Windows y APK de Android)

Usted **no tiene que ejecutar comandos ni instalar programas de desarrollo**. GitHub (gratis) compila todo por usted.
Estos pasos se hacen **solo desde el navegador**. Tiempo: ~15 min de trabajo y ~30-60 min de espera de GitHub.

## Una sola vez
1. Entre a **github.com** e inicie sesión (o cree una cuenta gratuita).
2. Arriba a la derecha: **+ → New repository**. Nombre: `math-universe`. Marque **Private**. Pulse **Create repository**.
3. En la página del repositorio: **uploading an existing file** (o **Add file → Upload files**).
   Arrastre **solo el archivo** `MATH_UNIVERSE_fase10.zip` (sin descomprimirlo). Espere a que termine y pulse **Commit changes**.
4. **Add file → Create new file**. En el nombre escriba exactamente: `.github/workflows/construir.yml`
   (al escribir las `/` GitHub crea las carpetas). Abra con el Bloc de notas el archivo `construir.yml` que le entregué, **copie todo su contenido** y péguelo en el cuadro grande. Pulse **Commit changes**.

## Obtener los instaladores
5. Pestaña **Actions** (arriba). Verá «Construir MATH UNIVERSE». Si no empezó sola: entre en él → **Run workflow**.
6. Espere a que los dos trabajos (**windows** y **android**) terminen (círculo verde ✔). Tarda 30-60 minutos.
7. Entre en la ejecución terminada y baje a **Artifacts**: descargue
   - **MATH_UNIVERSE_Windows** → dentro está `MATH_UNIVERSE_Setup_0.4.0.exe` (instalador) y `MATH_UNIVERSE_portable_windows.zip`.
   - **MATH_UNIVERSE_Android** → dentro está `MATH_UNIVERSE_android.apk`.
8. Windows: haga doble clic en `MATH_UNIVERSE_Setup_0.4.0.exe` (si Windows avisa «SmartScreen», pulse *Más información → Ejecutar de todas formas*: el instalador no está firmado todavía).
   Android: pase el `.apk` al teléfono, ábralo y permita «instalar apps de esta fuente».

## Si algo sale en rojo ✖
Entre en el trabajo que falló, pulse el paso en rojo y **copie su texto** (o haga una captura) y envíemelo. Yo lo corrijo y le entrego un ZIP nuevo; usted solo vuelve a subirlo (paso 3, reemplazando el ZIP) y a pulsar **Run workflow**.
**Esto es esperable en la primera compilación:** el cliente Flutter y la compilación de Android se escribieron sin poder compilarlos en mi entorno (ver `docs/INFORME_ENTREGA_FASE10.md`).

## Qué hace la aplicación
Pestañas **Calculadora** (evaluar, simplificar, expandir, factorizar, resolver, derivar, integrar, límites), **Matrices** (suma, resta, producto, transpuesta, determinante, inversa, rango, forma escalonada, sistemas Ax=b; aritmética exacta) e **Historial** (se guarda en su equipo). Cada resultado indica si pasó la verificación independiente. Sin internet.
