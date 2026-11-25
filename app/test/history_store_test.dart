import 'package:flutter_test/flutter_test.dart';
import 'package:math_universe_app/data/history_store.dart';

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
}
