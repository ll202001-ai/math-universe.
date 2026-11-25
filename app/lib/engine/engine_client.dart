import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'models.dart';

/// Canal de lineas con el motor (proceso en Windows). Se abstrae para poder probar el cliente sin proceso real.
abstract class LineTransport {
  Stream<String> get lines;
  void writeLine(String line);
  Future<void> kill();
}

class ProcessTransport implements LineTransport {
  ProcessTransport._(this._p) : lines = _p.stdout.transform(utf8.decoder).transform(const LineSplitter()).asBroadcastStream() {
    // El motor no escribe en stderr en uso normal; se vacia para que el proceso nunca se bloquee.
    _p.stderr.drain<void>();
  }

  final Process _p;
  @override
  final Stream<String> lines;

  static Future<ProcessTransport> start(String python, String script, String workingDir, {bool isolated = false}) async {
    // -I (aislado): ignora PYTHONPATH/PYTHONHOME y el site del usuario; solo para el Python empaquetado con la app.
    final p = await Process.start(python, [if (isolated) '-I', '-X', 'utf8', script],
        workingDirectory: workingDir, environment: {'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8'});
    return ProcessTransport._(p);
  }

  @override
  void writeLine(String line) => _p.stdin.add(utf8.encode('$line\n'));

  @override
  Future<void> kill() async {
    _p.kill();
  }
}

abstract class EngineClient {
  Future<EngineResponse> send(Map<String, dynamic> request, {Duration? timeout});
  Future<void> dispose();
}

/// Cliente JSON Lines: una solicitud a la vez, correlacion por request_id, reinicio del motor si no responde (cancelacion real).
class JsonLinesEngineClient implements EngineClient {
  JsonLinesEngineClient(this._factory);

  final Future<LineTransport> Function() _factory;
  LineTransport? _t;
  StreamSubscription<String>? _sub;
  final Map<int, Completer<EngineResponse>> _pending = {};
  int _next = 1;
  Future<void> _chain = Future<void>.value();

  @override
  Future<EngineResponse> send(Map<String, dynamic> request, {Duration? timeout}) {
    final c = Completer<EngineResponse>();
    _chain = _chain.then((_) async {
      try {
        c.complete(await _sendOne(request, timeout));
      } catch (e) {
        c.complete(EngineResponse.local('internal_error', 'ENGINE_UNAVAILABLE', 'No se pudo iniciar el motor local: $e'));
      }
    });
    return c.future;
  }

  Future<EngineResponse> _sendOne(Map<String, dynamic> request, Duration? timeout) async {
    final t = await _ensure();
    final id = _next++;
    final done = Completer<EngineResponse>();
    _pending[id] = done;
    t.writeLine(jsonEncode({...request, 'request_id': id}));
    final ms = (request['timeout_ms'] is int) ? request['timeout_ms'] as int : 10000;
    final limit = timeout ?? Duration(milliseconds: ms + 3000);
    try {
      return await done.future.timeout(limit);
    } on TimeoutException {
      _pending.remove(id);
      await _restart();
      return EngineResponse.local('timeout', 'TIMEOUT', 'El motor no respondio a tiempo; se cancelo y se reinicio.');
    }
  }

  Future<LineTransport> _ensure() async {
    final cur = _t;
    if (cur != null) return cur;
    final t = await _factory();
    _t = t;
    _sub = t.lines.listen(_onLine, onDone: _onClosed, onError: (_) => _onClosed());
    return t;
  }

  void _onLine(String line) {
    try {
      final m = jsonDecode(line);
      if (m is! Map<String, dynamic>) return;
      final id = m['request_id'];
      final c = (id is int) ? _pending.remove(id) : null;
      c?.complete(EngineResponse(m));
    } on FormatException {
      // linea que no es JSON: se ignora (el motor solo emite JSON)
    }
  }

  void _onClosed() {
    _t = null;
    _sub = null;
    final pend = Map<int, Completer<EngineResponse>>.from(_pending);
    _pending.clear();
    for (final c in pend.values) {
      if (!c.isCompleted) c.complete(EngineResponse.local('internal_error', 'ENGINE_CLOSED', 'El motor se cerro inesperadamente.'));
    }
  }

  Future<void> _restart() async {
    final t = _t;
    final s = _sub;
    _t = null;
    _sub = null;
    await s?.cancel();
    await t?.kill();
  }

  @override
  Future<void> dispose() async {
    await _restart();
    _onClosed();
  }
}

/// Localiza el motor empaquetado junto al ejecutable (instalador) o, en desarrollo, mediante MATH_UNIVERSE_ENGINE_DIR.
class EngineLocation {
  EngineLocation(this.python, this.script, this.workingDir, {this.packaged = false});
  final String python;
  final String script;
  final String workingDir;

  /// true: Python embebido instalado junto a la app (se ejecuta en modo aislado).
  final bool packaged;

  static EngineLocation? find() {
    final env = Platform.environment['MATH_UNIVERSE_ENGINE_DIR'];
    if (env != null && File('$env${Platform.pathSeparator}run_server.py').existsSync()) {
      return EngineLocation(Platform.environment['MATH_UNIVERSE_PYTHON'] ?? (Platform.isWindows ? 'python' : 'python3'),
          '$env${Platform.pathSeparator}run_server.py', env);
    }
    final exeDir = File(Platform.resolvedExecutable).parent.path;
    final sep = Platform.pathSeparator;
    // pythonw.exe: mismo interprete sin ventana de consola (la comunicacion va por tuberias stdin/stdout).
    final pyw = '$exeDir${sep}engine_runtime${sep}python${sep}pythonw.exe';
    final pyc = '$exeDir${sep}engine_runtime${sep}python${sep}python.exe';
    final py = File(pyw).existsSync() ? pyw : pyc;
    final eng = '$exeDir${sep}engine_runtime${sep}engine';
    if (File(py).existsSync() && File('$eng${sep}run_server.py').existsSync()) {
      return EngineLocation(py, '$eng${sep}run_server.py', eng, packaged: true);
    }
    return null;
  }
}

class UnavailableEngineClient implements EngineClient {
  UnavailableEngineClient(this.reason);
  final String reason;
  @override
  Future<EngineResponse> send(Map<String, dynamic> request, {Duration? timeout}) async =>
      EngineResponse.local('internal_error', 'ENGINE_UNAVAILABLE', reason);
  @override
  Future<void> dispose() async {}
}
