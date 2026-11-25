import 'package:flutter_test/flutter_test.dart';
import 'package:math_universe_app/engine/engine_client.dart';

import 'fakes.dart';

void main() {
  test('correlaciona respuestas por request_id y reutiliza el proceso', () async {
    var starts = 0;
    final c = JsonLinesEngineClient(() async {
      starts++;
      return FakeTransport();
    });
    final a = await c.send({'operation': 'ping'});
    final b = await c.send({'operation': 'evaluate', 'expression': '1+1'});
    expect(a.exactResult, 'eco:ping');
    expect(b.exactResult, 'eco:evaluate');
    expect(starts, 1);
    await c.dispose();
  });

  test('solicitudes en paralelo se atienden en orden y cada una recibe la suya', () async {
    final c = JsonLinesEngineClient(() async => FakeTransport());
    final rs = await Future.wait([for (var i = 0; i < 5; i++) c.send({'operation': 'op$i'})]);
    expect([for (final r in rs) r.exactResult], ['eco:op0', 'eco:op1', 'eco:op2', 'eco:op3', 'eco:op4']);
    await c.dispose();
  });

  test('motor mudo: plazo agotado, devuelve timeout, mata el proceso y arranca uno nuevo', () async {
    final transports = <FakeTransport>[];
    final c = JsonLinesEngineClient(() async {
      final t = FakeTransport(mute: transports.isEmpty);
      transports.add(t);
      return t;
    });
    final r1 = await c.send({'operation': 'evaluate'}, timeout: const Duration(milliseconds: 150));
    expect(r1.status, 'timeout');
    expect(transports.first.killed, isTrue);
    final r2 = await c.send({'operation': 'ping'});
    expect(r2.exactResult, 'eco:ping');
    expect(transports.length, 2);
    await c.dispose();
  });

  test('lineas que no son JSON se ignoran sin romper el cliente', () async {
    final t = FakeTransport();
    final c = JsonLinesEngineClient(() async => t);
    await c.send({'operation': 'ping'});
    t.emitRaw('esto no es json');
    t.emitRaw('[1,2,3]');
    final r = await c.send({'operation': 'ping'});
    expect(r.exactResult, 'eco:ping');
    await c.dispose();
  });

  test('si el motor se cierra con una solicitud pendiente, se informa el error', () async {
    final t = FakeTransport(mute: true);
    final c = JsonLinesEngineClient(() async => t);
    final f = c.send({'operation': 'evaluate'}, timeout: const Duration(seconds: 5));
    await Future<void>.delayed(const Duration(milliseconds: 50));
    await t.closeStream();
    final r = await f;
    expect(r.errorCode, 'ENGINE_CLOSED');
  });

  test('si no se puede iniciar el motor: error claro, no excepcion', () async {
    final c = JsonLinesEngineClient(() async => throw Exception('no existe python'));
    final r = await c.send({'operation': 'ping'});
    expect(r.errorCode, 'ENGINE_UNAVAILABLE');
    expect(r.errorMessage, contains('no existe python'));
  });
}
