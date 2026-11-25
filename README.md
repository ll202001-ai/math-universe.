# MATH UNIVERSE · fase 10 (motor 0.4.0 · contrato 1.1)

Calculadora matemática exacta, sin internet. **Empiece por `LEEME_PRIMERO.md`.**

| Carpeta | Contenido |
|---|---|
| `engine/` | Motor Python 0.4.0 (parser, CAS exacto, **álgebra lineal integrada**, verificación independiente, pruebas) |
| `app/` | Cliente Flutter (Windows y Android): calculadora, matrices, historial SQLite, comunicación con el motor |
| `tools/ci/`, `.github/workflows/`, `installer/` | Compilación automática en GitHub (instalador de Windows y APK) |
| `versiones_anteriores/` | Fase 8 y fase 9B **intactas** con sus manifiestos y hashes |
| `docs/` | Contrato, arquitectura, informes (`INFORME_ENTREGA_FASE10.md` es el principal) |
| `MANIFIESTO_SHA256.txt` | Hash de cada archivo de este paquete (`python tools/manifiesto.py` lo verifica) |
