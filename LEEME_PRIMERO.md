# Cómo instalar MATH UNIVERSE

No tiene que instalar Python, Flutter, SymPy ni ninguna herramienta de programación. Todo va dentro del instalador.

## Descargar
En la página del repositorio en GitHub, sección **Releases** (columna derecha), abra la versión más reciente
(`MATH UNIVERSE 0.5.0`) y descargue:

| Equipo | Archivo |
|---|---|
| Windows 10 u 11 (64 bits) | `MATH_UNIVERSE_SETUP.exe` |
| Android 7.0 o superior (64 bits) | `MATH_UNIVERSE.apk` |

Cada versión publicada se compiló y se verificó automáticamente: se instaló sin conexión a internet y pasó su autoprueba
(ver los archivos `AUTOPRUEBA_WINDOWS.json` y `AUTOPRUEBA_ANDROID.txt` de la misma versión).

## Windows
1. Haga doble clic en `MATH_UNIVERSE_SETUP.exe`.
2. Si aparece «Windows protegió su PC» (SmartScreen): **Más información → Ejecutar de todas formas**. El aviso sale porque
   el instalador todavía no está firmado con un certificado comercial.
3. Siga el asistente. No pide permisos de administrador. Se crean accesos directos en el menú Inicio y en el escritorio.
4. Para desinstalar: Configuración → Aplicaciones → MATH UNIVERSE → Desinstalar.

## Android
1. Copie `MATH_UNIVERSE.apk` al teléfono (o descárguelo desde el teléfono) y ábralo.
2. Permita «Instalar aplicaciones de esta fuente» cuando el teléfono lo pida.
3. Si Google Play Protect avisa de una app desconocida: **Instalar de todas formas** (el APK no está publicado en Play Store).

## Primer uso
- Escriba un problema, por ejemplo `x^2-5*x+6=0`, y pulse el botón grande. La app sugiere la operación y usted puede
  cambiarla (Calcular, Simplificar, Factorizar, Resolver, Derivar, Integrar, Límite).
- Toque un ejemplo para insertarlo, o use el teclado científico (pestañas Básico, Funciones y Álgebra).
- «Procedimiento y verificación» muestra cómo se obtuvo el resultado y cómo se comprobó.
- Menú (⋮) → **Comprobar instalación**: ejecuta una autoprueba completa en su equipo, sin internet.
- Menú (⋮) → **Acerca de y limitaciones**: lo que la app hace y lo que todavía no hace.

Funciona sin conexión a internet. Ningún cálculo ni dato sale de su equipo.
