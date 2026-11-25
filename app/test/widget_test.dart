import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:math_universe_app/data/history_store.dart';
import 'package:math_universe_app/main.dart';

import 'fakes.dart';

Map<String, dynamic> _handler(Map<String, dynamic> req) {
  switch (req['operation']) {
    case 'ping':
      return okResponse('pong');
    case 'matrix_det':
      return okResponse('-2', data: {'determinant': '-2', 'invertible': true});
    case 'matrix_inverse':
      return okResponse('[[-2, 1], [3/2, -1/2]]', data: {'matrix': [['-2', '1'], ['3/2', '-1/2']]});
    default:
      return okResponse('resultado:${req['expression']}');
  }
}

void main() {
  testWidgets('calcula una expresion, muestra el resultado y su verificacion, y lo guarda en el historial', (tester) async {
    final eng = FakeEngine(_handler);
    final store = MemoryHistoryStore();
    await tester.pumpWidget(MathUniverseApp(engine: eng, store: store));
    await tester.pumpAndSettle();
    expect(find.text('Motor local listo'), findsOneWidget);

    await tester.enterText(find.byKey(const Key('campo_expresion')), '1/3+1/6');
    await tester.tap(find.byKey(const Key('boton_calcular')));
    await tester.pumpAndSettle();

    expect(find.text('resultado:1/3+1/6'), findsOneWidget);
    expect(find.text('Verificado de forma independiente'), findsOneWidget);
    final sent = eng.lastCalc;
    expect(sent['operation'], 'evaluate');
    expect(sent['expression'], '1/3+1/6');
    expect((await store.list()).length, 1);
  });

  testWidgets('matrices: envia structured_input exacto y muestra la tabla del resultado', (tester) async {
    final eng = FakeEngine(_handler);
    await tester.pumpWidget(MathUniverseApp(engine: eng, store: MemoryHistoryStore()));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Matrices'));
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('selector_operacion_matriz')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Inversa').last);
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('boton_calcular_matriz')));
    await tester.pumpAndSettle();

    final sent = eng.lastCalc;
    expect(sent['operation'], 'matrix_inverse');
    expect(sent['structured_input'], {'a': [['1', '2'], ['3', '4']]});
    expect(find.byKey(const Key('tabla_matriz')), findsOneWidget);
    expect(find.text('3/2'), findsOneWidget);
  });

  testWidgets('matriz irregular: error local, no se llama al motor', (tester) async {
    final eng = FakeEngine(_handler);
    await tester.pumpWidget(MathUniverseApp(engine: eng, store: MemoryHistoryStore()));
    await tester.pumpAndSettle();
    final before = eng.received.length;
    await tester.tap(find.text('Matrices'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byKey(const Key('campo_matriz_a')), '1 2\n3');
    await tester.tap(find.byKey(const Key('boton_calcular_matriz')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('error_local')), findsOneWidget);
    expect(eng.received.length, before);
  });

  testWidgets('error del motor se muestra como error, no como resultado', (tester) async {
    final eng = FakeEngine((req) => req['operation'] == 'ping'
        ? okResponse('pong')
        : {
            'status': 'domain_error',
            'error': {'code': 'DOMAIN_ERROR', 'message': 'La matriz es singular'},
            'verification': {'status': 'not_performed', 'method': null},
          });
    await tester.pumpWidget(MathUniverseApp(engine: eng, store: MemoryHistoryStore()));
    await tester.pumpAndSettle();
    await tester.enterText(find.byKey(const Key('campo_expresion')), '1/0');
    await tester.tap(find.byKey(const Key('boton_calcular')));
    await tester.pumpAndSettle();
    expect(find.text('Error de dominio'), findsOneWidget);
    expect(find.text('La matriz es singular'), findsOneWidget);
    expect(find.text('Sin verificación independiente'), findsOneWidget);
    expect(find.byKey(const Key('texto_resultado')), findsNothing);
  });

  testWidgets('motor no disponible se informa en la barra superior', (tester) async {
    final eng = FakeEngine((req) => {
          'status': 'internal_error',
          'error': {'code': 'ENGINE_UNAVAILABLE', 'message': 'no hay motor'},
        });
    await tester.pumpWidget(MathUniverseApp(engine: eng, store: MemoryHistoryStore()));
    await tester.pumpAndSettle();
    expect(find.textContaining('Motor no disponible'), findsOneWidget);
  });

  testWidgets('con "=" sugiere Resolver, y el usuario puede elegir otra operacion antes de calcular', (tester) async {
    final eng = FakeEngine(_handler);
    await tester.pumpWidget(MathUniverseApp(engine: eng, store: MemoryHistoryStore()));
    await tester.pumpAndSettle();
    await tester.enterText(find.byKey(const Key('campo_expresion')), 'x^2-5*x+6=0');
    await tester.pump();
    expect(find.textContaining('Operación sugerida: Resolver'), findsOneWidget);
    await tester.tap(find.byKey(const Key('boton_calcular')));
    await tester.pumpAndSettle();
    expect(eng.lastCalc['operation'], 'solve');

    await tester.enterText(find.byKey(const Key('campo_expresion')), 'x^2-5*x+6');
    await tester.tap(find.byKey(const Key('op_factor')));
    await tester.pump();
    expect(find.textContaining('Operación elegida: Factorizar'), findsOneWidget);
    await tester.tap(find.byKey(const Key('boton_calcular')));
    await tester.pumpAndSettle();
    expect(eng.lastCalc['operation'], 'factor');
    expect(eng.lastCalc['expression'], 'x^2-5*x+6');
  });

  testWidgets('el teclado cientifico inserta en el cursor y calcula', (tester) async {
    tester.view.physicalSize = const Size(1400, 1000);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);
    final eng = FakeEngine(_handler);
    await tester.pumpWidget(MathUniverseApp(engine: eng, store: MemoryHistoryStore()));
    await tester.pumpAndSettle();
    for (final k in ['1', '+', '1']) {
      await tester.tap(find.bySemanticsLabel(k == '+' ? 'mas' : k).first);
      await tester.pump();
    }
    expect(find.text('1+1'), findsOneWidget);
    await tester.tap(find.byKey(const Key('tecla_borrar')));
    await tester.pump();
    expect(find.text('1+'), findsOneWidget);
    await tester.tap(find.text('Funciones'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('sin'));
    await tester.pump();
    expect(find.text('1+sin()'), findsOneWidget);
    await tester.tap(find.byKey(const Key('tecla_ac')));
    await tester.pump();
    expect(find.text('1+sin()'), findsNothing);
  });

  testWidgets('el panel de procedimiento muestra metodo y verificacion reales del motor', (tester) async {
    tester.view.physicalSize = const Size(1000, 2400);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);
    final eng = FakeEngine((req) => req['operation'] == 'ping'
        ? okResponse('pong')
        : {
            ...okResponse('x = 2, x = 3'),
            'method': 'factorizacion_racional_y_formula_cuadratica',
            'verification': {'status': 'passed', 'method': 'sustitucion_exacta_en_la_ecuacion_original'},
            'parsed_input': {'canonical': 'x^2 - 5*x + 6 = 0'},
          });
    await tester.pumpWidget(MathUniverseApp(engine: eng, store: MemoryHistoryStore()));
    await tester.pumpAndSettle();
    await tester.enterText(find.byKey(const Key('campo_expresion')), 'x^2-5*x+6=0');
    await tester.tap(find.byKey(const Key('boton_calcular')));
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.text('Procedimiento y verificación'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Procedimiento y verificación'));
    await tester.pumpAndSettle();
    expect(find.textContaining('Factorización racional y fórmula cuadrática', findRichText: true), findsOneWidget);
    expect(find.textContaining('Sustitución exacta de cada solución', findRichText: true), findsOneWidget);
    expect(find.textContaining('x^2 - 5*x + 6 = 0', findRichText: true), findsOneWidget);
  });
}
