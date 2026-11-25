import 'dart:io';

import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'package:sqflite/sqflite.dart' as sqflite_plugin;
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

class HistoryEntry {
  HistoryEntry({this.id, required this.createdAt, required this.kind, required this.operation, required this.input, required this.result, required this.status});
  final int? id;
  final DateTime createdAt;
  final String kind; // 'calculo' | 'matriz'
  final String operation;
  final String input;
  final String result;
  final String status;
}

abstract class HistoryStore {
  Future<void> add(HistoryEntry e);
  Future<List<HistoryEntry>> list({String? query, int limit = 200});
  Future<void> delete(int id);
  Future<void> clear();
  Future<void> close();
}

/// Historial local en SQLite (sqflite en Android, sqflite_common_ffi en Windows).
class SqliteHistoryStore implements HistoryStore {
  SqliteHistoryStore._(this._db);
  final Database _db;

  static Future<SqliteHistoryStore> open({String? path}) async {
    if (Platform.isWindows || Platform.isLinux || Platform.isMacOS) {
      sqfliteFfiInit(); // SQLite nativo empaquetado por package:sqlite3 (sin dependencias del sistema)
      databaseFactory = databaseFactoryFfi;
    } else {
      databaseFactory = sqflite_plugin.databaseFactorySqflitePlugin; // Android: SQLite del sistema via plugin
    }
    final target = path ?? p.join((await getApplicationSupportDirectory()).path, 'math_universe_historial.db');
    // singleInstance: false -> cada apertura es una conexion propia (la autoprueba cierra y reabre sin cerrar la de la app).
    final db = await openDatabase(target, version: 1, singleInstance: false, onCreate: (db, v) async {
      await db.execute('CREATE TABLE historial ('
          'id INTEGER PRIMARY KEY AUTOINCREMENT, creado TEXT NOT NULL, tipo TEXT NOT NULL, operacion TEXT NOT NULL, '
          'entrada TEXT NOT NULL, resultado TEXT NOT NULL, estado TEXT NOT NULL)');
      await db.execute('CREATE INDEX idx_historial_creado ON historial(creado DESC)');
    });
    return SqliteHistoryStore._(db);
  }

  @override
  Future<void> add(HistoryEntry e) async {
    await _db.insert('historial', {
      'creado': e.createdAt.toIso8601String(),
      'tipo': e.kind,
      'operacion': e.operation,
      'entrada': e.input,
      'resultado': e.result,
      'estado': e.status,
    });
  }

  @override
  Future<List<HistoryEntry>> list({String? query, int limit = 200}) async {
    final q = (query ?? '').trim();
    final rows = q.isEmpty
        ? await _db.query('historial', orderBy: 'creado DESC, id DESC', limit: limit)
        : await _db.query('historial',
            where: 'entrada LIKE ? OR resultado LIKE ? OR operacion LIKE ?',
            whereArgs: ['%$q%', '%$q%', '%$q%'],
            orderBy: 'creado DESC, id DESC',
            limit: limit);
    return rows
        .map((r) => HistoryEntry(
            id: r['id'] as int,
            createdAt: DateTime.parse(r['creado'] as String),
            kind: r['tipo'] as String,
            operation: r['operacion'] as String,
            input: r['entrada'] as String,
            result: r['resultado'] as String,
            status: r['estado'] as String))
        .toList();
  }

  @override
  Future<void> delete(int id) async {
    await _db.delete('historial', where: 'id = ?', whereArgs: [id]);
  }

  @override
  Future<void> clear() async {
    await _db.delete('historial');
  }

  @override
  Future<void> close() => _db.close();
}

/// Historial en memoria (pruebas y respaldo si SQLite no se pudo abrir).
class MemoryHistoryStore implements HistoryStore {
  final List<HistoryEntry> _items = [];
  int _id = 0;

  @override
  Future<void> add(HistoryEntry e) async =>
      _items.insert(0, HistoryEntry(id: ++_id, createdAt: e.createdAt, kind: e.kind, operation: e.operation, input: e.input, result: e.result, status: e.status));

  @override
  Future<List<HistoryEntry>> list({String? query, int limit = 200}) async {
    final q = (query ?? '').trim().toLowerCase();
    return _items.where((e) => q.isEmpty || '${e.input} ${e.result} ${e.operation}'.toLowerCase().contains(q)).take(limit).toList();
  }

  @override
  Future<void> delete(int id) async => _items.removeWhere((e) => e.id == id);
  @override
  Future<void> clear() async => _items.clear();
  @override
  Future<void> close() async {}
}
