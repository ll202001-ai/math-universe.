# INFORME DE VALIDACIÓN · MATH UNIVERSE motor 0.3.0

Fecha: 2026-11-24T15:04:17 · duración 122.6 s

## Veredicto
**VALIDACIÓN INCOMPLETA O CON HALLAZGOS: 1 prueba(s) OMITIDA(S) (no cuentan como aprobadas); SymPy no instalado; mpmath no instalado; comparación con SymPy NO ejecutada**

## Versiones registradas
| Componente | Versión |
|---|---|
| python | 3.13.18 |
| implementacion | CPython |
| sistema | Linux-6.18.44-fc-v819-x86_64-with-glibc2.39 |
| arquitectura | x86_64 |
| ejecutable | /usr/local/bin/python3 |
| sympy | NO INSTALADO (ModuleNotFoundError) |
| mpmath | NO INSTALADO (ModuleNotFoundError) |
| numpy | 2.5.3 |
| scipy | 1.18.1 |
| jsonschema | 4.26.0 |
| pytest | 9.1.1 |
| motor | 0.3.0 |

## 1. Pruebas automatizadas (pytest)
**Aprobadas: 489 · Falladas: 0 · Omitidas: 1** (las omitidas NO se cuentan como aprobadas)

| Archivo | Aprobadas | Falladas | Omitidas |
|---|---|---|---|
| test_08_sympy.py | 0 | 0 | 1 |
| test_01_exactas.py | 30 | 0 | 0 |
| test_02_simbolicas.py | 60 | 0 | 0 |
| test_03_dominio.py | 27 | 0 | 0 |
| test_04_ecuaciones_sistemas.py | 38 | 0 | 0 |
| test_05_entradas_y_aproximacion.py | 30 | 0 | 0 |
| test_06_seguridad_y_recursos.py | 32 | 0 | 0 |
| test_07_verificacion_negativa.py | 8 | 0 | 0 |
| test_09_auditoria.py | 68 | 0 | 0 |
| test_10_comparador.py | 22 | 0 | 0 |
| test_11_respaldo_simulado.py | 6 | 0 | 0 |
| test_12_no_soportado.py | 46 | 0 | 0 |
| test_13_windows_lint.py | 3 | 0 | 0 |
| test_14_hallazgos_windows.py | 119 | 0 | 0 |

Omitidas:
- `tests/test_08_sympy.py [MÓDULO COMPLETO]` — Skipped: SymPy no está instalado en este entorno

## 2. Pruebas aleatorias (semillas fijas, oráculo independiente)
| Semilla | Simplificar | Derivar | Factorizar | Expandir | Integrar | Fallos |
|---|---|---|---|---|---|---|
| 1 | 299 | 300 | 250 | 250 | 120 | 0 |
| 7 | 293 | 296 | 250 | 250 | 120 | 0 |
| 99 | 296 | 300 | 250 | 250 | 120 | 0 |
| 2024 | 295 | 298 | 250 | 250 | 120 | 0 |
| 12345 | 296 | 299 | 250 | 250 | 120 | 0 |
| 31337 | 298 | 299 | 250 | 250 | 120 | 0 |

## 3. Auditoría con oráculo independiente (NumPy/SciPy/diferencias finitas, sin usar el parser del motor)
Total 208: **correctos 200 · no soportados (declarados, NO cuentan como correctos) 8 · fallos 0**

| Categoría | Correctos | No soportados | Fallos |
|---|---|---|---|
| simplificación | 15 | 0 | 0 |
| factorización | 26 | 0 | 0 |
| ecuaciones | 23 | 0 | 0 |
| sistemas | 33 | 0 | 0 |
| despeje | 13 | 1 | 0 |
| derivadas | 21 | 0 | 0 |
| integrales | 32 | 7 | 0 |
| límites | 26 | 0 | 0 |
| numérico | 11 | 0 | 0 |

No soportados (el motor lo declara; no es un resultado):
- despeje: `A=pi*r^2 → r` — Despeje literal solo implementado para grado 1 en 'r' (grado 2)
- integrales: `∫[0,4] sqrt(x)` — Integral de sqrt no implementada
- integrales: `∫[0,1] tan(x)` — Integral de tan no implementada
- integrales: `∫ sin(x)^2 dx` — Producto/potencia de funciones no soportado por el integrador propio
- integrales: `∫ cos(x)*sin(x) dx` — Producto/potencia de funciones no soportado por el integrador propio
- integrales: `∫ tan(x) dx` — Integral de tan no implementada
- integrales: `∫ sqrt(x) dx` — Integral de sqrt no implementada
- integrales: `∫ 1/sqrt(x) dx` — Cociente con funciones trascendentes: no implementado

## 4. Comparación motor propio vs SymPy
**NO EJECUTADA** — SymPy/mpmath no instalados: No module named 'sympy'

## Cómo interpretar
- *Implementado* = existe código; *probado* = pasa las pruebas anteriores; *pendiente* = ver docs/FUNCIONES.md.
- Este informe lo genera `tools/validar_todo.py`; no contiene resultados escritos a mano.
