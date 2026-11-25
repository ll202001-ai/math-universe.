import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/services.dart';

import 'engine_client.dart';
import 'models.dart';

/// Android: el motor Python corre dentro de la app (Chaquopy) y se invoca por un MethodChannel.
class AndroidEngineClient implements EngineClient {
  static const MethodChannel _ch = MethodChannel('math_universe/engine');
  int _next = 1;

  @override
  Future<EngineResponse> send(Map<String, dynamic> request, {Duration? timeout}) async {
    final id = _next++;
    try {
      final ms = (request['timeout_ms'] is int) ? request['timeout_ms'] as int : 10000;
      final out = await _ch
          .invokeMethod<String>('handle', jsonEncode({...request, 'request_id': id}))
          .timeout(timeout ?? Duration(milliseconds: ms + 5000));
      final m = jsonDecode(out ?? '{}');
      return EngineResponse(m is Map<String, dynamic> ? m : <String, dynamic>{});
    } on TimeoutException {
      return EngineResponse.local('timeout', 'TIMEOUT', 'El motor no respondio a tiempo.');
    } on PlatformException catch (e) {
      return EngineResponse.local('internal_error', 'ENGINE_UNAVAILABLE', 'Motor Android no disponible: ${e.message}');
    } on MissingPluginException {
      return EngineResponse.local('internal_error', 'ENGINE_UNAVAILABLE', 'Esta compilacion de Android no incluye el motor Python.');
    }
  }

  @override
  Future<void> dispose() async {}
}

EngineClient createEngineClient() {
  if (Platform.isAndroid) return AndroidEngineClient();
  final loc = EngineLocation.find();
  if (loc == null) {
    return UnavailableEngineClient(
        'No se encontro el motor local (carpeta engine_runtime). Reinstale MATH UNIVERSE con el instalador.');
  }
  return JsonLinesEngineClient(() => ProcessTransport.start(loc.python, loc.script, loc.workingDir, isolated: loc.packaged));
}
