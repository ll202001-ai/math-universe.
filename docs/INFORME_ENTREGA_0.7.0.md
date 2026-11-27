# Informe de entrega · MATH UNIVERSE 0.7.0

## Qué cambia
**Entrada matemática rediseñada** (ADR-15):
- Editor visual estructurado: fracción con numerador y denominador editables, potencias, subíndices, raíces con índice,
  valor absoluto, suelo/techo, funciones, log en base b, integral definida/indefinida, Σ, Π, límite, d/dx, matrices m×n
  y sistemas. Casillas vacías visibles; cursor con ← → ↑ ↓ y Tab; deshacer y rehacer; copiar y pegar.
- Teclado de 10 pestañas: Básico, Álgebra, Cálculo, Trigonometría, Matrices y vectores, Estadística, Ecuaciones,
  Griegas, Lógica y conjuntos, Funciones especiales. Fila de control (mover, siguiente casilla, deshacer, rehacer,
  borrar, AC) y de acciones (Simplificar, Expandir, Factorizar, Resolver, =).
- Teclado físico: `/` crea fracción con lo anterior, `^` exponente, `_` subíndice, palabras → funciones y griegas,
  Ctrl+Z/Y/C/V, Enter.
- Hoja de trabajo: varias expresiones en bloques con su resultado; tocar un bloque lo reabre para editar y recalcular.

**Motor 0.7.0 / contrato 1.3** (ADR-16): sumatorias y productorias, sustitución, matrices simbólicas, lógica
proposicional, conjuntos, derivación implícita, funciones especiales, `%` y log en base b. Cada operación tiene una
comprobación independiente.

## Pruebas
- Motor: 950 pruebas (incluye `test_31_motor_070.py` con valores conocidos a mano y verificaciones saboteadas).
- App: 50 pruebas Flutter: modelo del editor (12), widgets (construir (x²+3x+2)/(x+1) solo con botones, plantillas de
  integral y Σ enviadas como operación del motor, plantilla incompleta explicada sin calcular) y la autoprueba completa
  contra el motor real.
- Autoprueba de la app instalada: 33 comprobaciones (17 de 0.5.0, 8 de 0.6.0, 8 de 0.7.0, incluida una fracción
  construida con las acciones del editor y enviada al motor). El CI la ejecuta en Windows sin red y en Android en modo
  avión antes de publicar.

## Limitaciones
Ver `LIMITACIONES.md`. En particular: tocar la fórmula no coloca el cursor en el punto exacto (se navega con flechas y
Tab); integrales, Σ, Π, límites y d/dx deben ser la expresión completa de un bloque.
