@Tags(['motor_real'])
library;

import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:math_universe_app/data/history_store.dart';
import 'package:math_universe_app/diagnostics/autotest.dart';
import 'package:math_universe_app/engine/engine_client.dart';

/// La MISMA autoprueba que ejecuta la app instalada, aqui contra el motor Python real (con SymPy y mpmath) y un
/// historial SQLite real en disco. Requiere MATH_UNIVERSE_ENGINE_DIR (lo define la integracion continua).
void main() {
  test('autoprueba completa: pruebas de aceptacion + SymPy + SQLite (cerrar y reabrir)', () async {
    final loc = EngineLocation.find();
    if (Platform.environment['MATH_UNIVERSE_ENGINE_DIR'] == null || loc == null) {
      fail('MATH_UNIVERSE_ENGINE_DIR no esta definido (esta prueba debe ejecutarse en CI)');
    }
    final dir = await Directory.systemTemp.createTemp('mu_autotest');
    final db = '${dir.path}${Platform.pathSeparator}historial.db';
    final c = JsonLinesEngineClient(() => ProcessTransport.start(loc.python, loc.script, loc.workingDir));
    final rep = await runAutotest(c, () => SqliteHistoryStore.open(path: db));
    for (final k in rep.checks) {
      // ignore: avoid_print
      print('${k.ok ? 'OK   ' : 'FALLA'} ${k.name} :: ${k.detail}');
    }
    expect(rep.failed, 0, reason: rep.checks.where((k) => !k.ok).map((k) => '${k.name}: ${k.detail}').join('\n'));
    expect(rep.checks.length, greaterThanOrEqualTo(33));
    await c.dispose();
    await dir.delete(recursive: true);
  }, timeout: const Timeout(Duration(minutes: 5)));
}
