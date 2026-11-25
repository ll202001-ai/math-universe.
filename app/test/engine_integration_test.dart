@Tags(['motor_real'])
library;

import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:math_universe_app/engine/engine_client.dart';

/// Prueba REAL cliente Dart <-> motor Python (proceso, JSON Lines, UTF-8). Requiere Python y la variable MATH_UNIVERSE_ENGINE_DIR.
void main() {
  final dir = Platform.environment['MATH_UNIVERSE_ENGINE_DIR'];
  final loc = EngineLocation.find();

  test('cliente Dart con el motor real: ping, calculo, matrices, error y recuperacion', () async {
    if (dir == null || loc == null) {
      fail('MATH_UNIVERSE_ENGINE_DIR no esta definido o no contiene run_server.py (esta prueba debe ejecutarse en CI)');
    }
    final c = JsonLinesEngineClient(() => ProcessTransport.start(loc.python, loc.script, loc.workingDir));
    final ping = await c.send({'operation': 'ping'});
    expect(ping.status, 'success_exact');

    final ev = await c.send({'operation': 'evaluate', 'expression': '1/3+1/6'});
    expect(ev.exactResult, '1/2');

    final det = await c.send({'operation': 'matrix_det', 'structured_input': {'a': [['1', '2'], ['3', '4']]}});
    expect(det.exactResult, '-2');
    expect(det.verificationStatus, 'passed');

    final inv = await c.send({'operation': 'matrix_inverse', 'structured_input': {'a': [['2', '1'], ['1', '1']]}});
    expect(inv.matrix, [['1', '-1'], ['-1', '2']]);

    final sing = await c.send({'operation': 'matrix_inverse', 'structured_input': {'a': [['1', '2'], ['2', '4']]}});
    expect(sing.status, 'domain_error');
    expect(sing.exactResult, isNull);

    final sol = await c.send({'operation': 'matrix_solve', 'structured_input': {'a': [['1', '1'], ['1', '-1']], 'b': [['3'], ['1']]}});
    expect(sol.data['particular'], ['2', '1']);

    final utf = await c.send({'operation': 'simplify', 'expression': '(x^3-8)/(x-2)'});
    expect(utf.conditions.join(' '), contains('≠'), reason: 'los caracteres UTF-8 deben llegar intactos desde el motor');

    final huge = await c.send({'operation': 'evaluate', 'expression': '1e999999999', 'timeout_ms': 2000});
    expect(huge.status, 'invalid_input');
    await c.dispose();
  }, timeout: const Timeout(Duration(seconds: 90)));
}
