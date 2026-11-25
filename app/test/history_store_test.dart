import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:math_universe_app/data/history_store.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

HistoryEntry _e(String input, String result, {String kind = 'calculo'}) =>
    HistoryEntry(createdAt: DateTime.now(), kind: kind, operation: 'evaluate', input: input, result: result, status: 'success_exact');

Future<void> _contrato(HistoryStore s) async {
  await s.add(_e('1+1', '2'));
  await s.add(_e('x^2', '2*x'));
  await s.add(_e('A=1 2; 3 4', '-2', kind: 'matriz'));
  expect((await s.list()).length, 3);
  expect((await s.list()).first.input, startsWith('A='), reason: 'lo mas reciente primero');
  expect((await s.list(query: 'x^2')).map((e) => e.result), ['2*x']);
  expect((await s.list(query: 'no existe')), isEmpty);
  final fav = (await s.list(query: 'x^2')).single.id!;
  await s.setFavorite(fav, true);
  expect((await s.list(onlyFavorites: true)).map((e) => e.input), ['x^2']);
  expect((await s.list(query: 'A=', onlyFavorites: true)), isEmpty);
  final csv = historyToCsv(await s.list());
  expect(csv.split('\n').first, 'fecha;tipo;operacion;entrada;resultado;estado;favorito');
  expect(csv, contains('"x^2";"2*x";"success_exact";"si"'));
  await s.setFavorite(fav, false);
  expect(await s.list(onlyFavorites: true), isEmpty);
  final id = (await s.list(query: '1+1')).single.id!;
  await s.delete(id);
  expect((await s.list()).length, 2);
  await s.clear();
  expect(await s.list(), isEmpty);
}

void main() {
  test('historial en memoria cumple el contrato', () async => _contrato(MemoryHistoryStore()));

  test('historial SQLite cumple el mismo contrato (si hay libreria SQLite en este equipo)', () async {
    SqliteHistoryStore? s;
    try {
      s = await SqliteHistoryStore.open(path: ':memory:');
    } catch (e) {
      // No se cuenta como aprobada: queda marcada como omitida con el motivo.
      markTestSkipped('SQLite nativo no disponible en este entorno de pruebas: $e');
      return;
    }
    await _contrato(s);
    await s.close();
  });

  test('migracion del historial v1 (fase 10) a v2 conserva los datos y anade favoritos', () async {
    sqfliteFfiInit();
    final dir = await Directory.systemTemp.createTemp('mu_migr');
    final path = '${dir.path}${Platform.pathSeparator}h.db';
    final v1 = await databaseFactoryFfi.openDatabase(path,
        options: OpenDatabaseOptions(
            version: 1,
            onCreate: (db, v) async {
              await db.execute('CREATE TABLE historial (id INTEGER PRIMARY KEY AUTOINCREMENT, creado TEXT NOT NULL, tipo TEXT NOT NULL, '
                  'operacion TEXT NOT NULL, entrada TEXT NOT NULL, resultado TEXT NOT NULL, estado TEXT NOT NULL)');
              await db.insert('historial', {
                'creado': DateTime(2026, 11, 1).toIso8601String(),
                'tipo': 'calculo',
                'operacion': 'evaluate',
                'entrada': '1/3+1/6',
                'resultado': '1/2',
                'estado': 'success_exact'
              });
            }));
    await v1.close();
    final s = await SqliteHistoryStore.open(path: path);
    final items = await s.list();
    expect(items.single.input, '1/3+1/6');
    expect(items.single.favorite, isFalse);
    await s.setFavorite(items.single.id!, true);
    expect((await s.list(onlyFavorites: true)).single.result, '1/2');
    await s.close();
    await dir.delete(recursive: true);
  });
}
