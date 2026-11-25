import 'dart:async';
import 'dart:convert';

import 'package:math_universe_app/engine/engine_client.dart';
import 'package:math_universe_app/engine/models.dart';

/// Motor simulado para pruebas de interfaz: responde segun una funcion.
class FakeEngine implements EngineClient {
  FakeEngine(this.handler);
  final Map<String, dynamic> Function(Map<String, dynamic> req) handler;
  final List<Map<String, dynamic>> received = [];

  /// Ultima solicitud de CALCULO (excluye vista previa, graficas de fondo, catalogos y ping).
  Map<String, dynamic> get lastCalc =>
      received.lastWhere((r) => !const {'parse', 'plot', 'formulas', 'interpret', 'ping', 'capabilities'}.contains(r['operation']));

  @override
  Future<EngineResponse> send(Map<String, dynamic> request, {Duration? timeout}) async {
    received.add(request);
    return EngineResponse(handler(request));
  }

  @override
  Future<void> dispose() async {}
}

Map<String, dynamic> okResponse(String exact, {Map<String, dynamic>? data, String verification = 'passed'}) => {
      'api_version': '1.1',
      'status': 'success_exact',
      'exact_result': exact,
      'conditions': <String>[],
      'warnings': <String>[],
      'verification': {'status': verification, 'method': 'metodo de prueba'},
      'data': data ?? <String, dynamic>{},
      'elapsed_ms': 1.5,
    };

/// Transporte simulado: un "motor" que responde ping y eco, y puede quedarse mudo para probar el plazo.
class FakeTransport implements LineTransport {
  FakeTransport({this.mute = false});
  final bool mute;
  final StreamController<String> _out = StreamController<String>.broadcast();
  bool killed = false;

  @override
  Stream<String> get lines => _out.stream;

  @override
  void writeLine(String line) {
    if (mute) return;
    final req = jsonDecode(line) as Map<String, dynamic>;
    scheduleMicrotask(() => _out.add(jsonEncode({
          'request_id': req['request_id'],
          'api_version': '1.1',
          'status': 'success_exact',
          'exact_result': 'eco:${req['operation']}',
          'verification': {'status': 'not_performed', 'method': null},
        })));
  }

  void emitRaw(String line) => _out.add(line);
  Future<void> closeStream() => _out.close();

  @override
  Future<void> kill() async {
    killed = true;
  }
}
