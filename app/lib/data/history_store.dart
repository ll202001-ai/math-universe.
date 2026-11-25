import 'dart:io';

import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'package:sqflite/sqflite.dart' as sqflite_plugin;
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

class HistoryEntry {
  HistoryEntry(
      {this.id,
      required this.createdAt,
      required this.kind,
      required this.operation,
      required this.input,
      required this.result,
      required this.status,
      this.favorite = false});
  final int? id;
  final DateTime createdAt;
  final String kind; // 'calculo' | 'matriz'
  final String operation;
  final String input;
  final String result;
  final String status;
  final bool favorite;

  HistoryEntry copyWith({int? id, bool? favorite}) => HistoryEntry(
      id: id ?? this.id,
      createdAt: createdAt,
      kind: kind,
      operation: operation,
      input: input,
      result: result,
      status: status,
      favorite: favorite ?? this.favorite);
}

abstract class HistoryStore {
  Future<void> add(HistoryEntry e);
  Future<List<HistoryEntry>> list({String? query, int limit = 200, bool onlyFavorites = false});
  Future<void> setFavorite(int id, bool favorite);
  Future<void> delete(int id);
  Future<void> clear();
  Future<void> close();
}

/// Exporta entradas a CSV (separador ';', comillas dobles escapadas). Lo usa «Exportar historial».
String historyToCsv(List<HistoryEntry> items) {
  String q(String s) => '"${s.replaceAll('"', '""')}"';
  final b = StringBuffer('fecha;tipo;operacion;entrada;resultado;estado;favorito\n');
  for (final e in items) {
    b.writeln([e.createdAt.toIso8601String(), e.kind, e.operation, e.input, e.result, e.status, e.favorite ? 'si' : 'no']
        .map(q)
        .join(';'));
  }
  return b.toString();
}

/// Historial local en SQLite (sqflite en Android, sqflite_common_ffi en Windows).
/// Esquema v2: columna `favorito` (la migracion desde v1 conserva todos los datos).
class SqliteHistoryStore implements HistoryStore {
  SqliteHistoryStore._(this._db);
  final Database _db;

  static const schemaVersion = 2;

  static Future<SqliteHistoryStore> open({String? path}) async {
    if (Platform.isWindows || Platform.isLinux || Platform.isMacOS) {
      sqfliteFfiInit(); // SQLite nativo empaquetado por package:sqlite3 (sin dependencias del sistema)
      databaseFactory = databaseFactoryFfi;
    } else {
      databaseFactory = sqflite_plugin.databaseFactorySqflitePlugin; // Android: SQLite del sistema via plugin
    }
    final target = path ?? p.join((await getApplicationSupportDirectory()).path, 'math_universe_historial.db');
    // singleInstance: false -> cada apertura es una conexion propia (la autoprueba cierra y reabre sin cerrar la de la app).
    final db = await openDatabase(target, version: schemaVersion, singleInstance: false, onCreate: (db, v) async {
      await db.execute('CREATE TABLE historial ('
          'id INTEGER PRIMARY KEY AUTOINCREMENT, creado TEXT NOT NULL, tipo TEXT NOT NULL, operacion TEXT NOT NULL, '
          'entrada TEXT NOT NULL, resultado TEXT NOT NULL, estado TEXT NOT NULL, favorito INTEGER NOT NULL DEFAULT 0)');
      await db.execute('CREATE INDEX idx_historial_creado ON historial(creado DESC)');
    }, onUpgrade: (db, from, to) async {
      if (from < 2) await db.execute('ALTER TABLE historial ADD COLUMN favorito INTEGER NOT NULL DEFAULT 0');
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
      'favorito': e.favorite ? 1 : 0,
    });
  }

  @override
  Future<List<HistoryEntry>> list({String? query, int limit = 200, bool onlyFavorites = false}) async {
    final q = (query ?? '').trim();
    final where = <String>[];
    final args = <Object>[];
    if (q.isNotEmpty) {
      where.add('(entrada LIKE ? OR resultado LIKE ? OR operacion LIKE ?)');
      args.addAll(['%$q%', '%$q%', '%$q%']);
    }
    if (onlyFavorites) where.add('favorito = 1');
    final rows = await _db.query('historial',
        where: where.isEmpty ? null : where.join(' AND '),
        whereArgs: args.isEmpty ? null : args,
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
            status: r['estado'] as String,
            favorite: (r['favorito'] as int? ?? 0) == 1))
        .toList();
  }

  @override
  Future<void> setFavorite(int id, bool favorite) async {
    await _db.update('historial', {'favorito': favorite ? 1 : 0}, where: 'id = ?', whereArgs: [id]);
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
  Future<void> add(HistoryEntry e) async => _items.insert(0, e.copyWith(id: ++_id));

  @override
  Future<List<HistoryEntry>> list({String? query, int limit = 200, bool onlyFavorites = false}) async {
    final q = (query ?? '').trim().toLowerCase();
    return _items
        .where((e) => q.isEmpty || '${e.input} ${e.result} ${e.operation}'.toLowerCase().contains(q))
        .where((e) => !onlyFavorites || e.favorite)
        .take(limit)
        .toList();
  }

  @override
  Future<void> setFavorite(int id, bool favorite) async {
    final i = _items.indexWhere((e) => e.id == id);
    if (i >= 0) _items[i] = _items[i].copyWith(favorite: favorite);
  }

  @override
  Future<void> delete(int id) async => _items.removeWhere((e) => e.id == id);
  @override
  Future<void> clear() async => _items.clear();
  @override
  Future<void> close() async {}
}
