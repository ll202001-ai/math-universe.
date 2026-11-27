import 'package:flutter/material.dart';
import 'package:flutter_math_fork/flutter_math.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:math_universe_app/data/history_store.dart';
import 'package:math_universe_app/engine/models.dart';
import 'package:math_universe_app/main.dart';
import 'package:math_universe_app/ui/engineering_page.dart';
import 'package:math_universe_app/ui/graph_page.dart';
import 'package:math_universe_app/ui/result_view.dart';

import 'fakes.dart';

Future<void> _big(WidgetTester t) async {
  t.view.physicalSize = const Size(1200, 2000);
  t.view.devicePixelRatio = 1.0;
  addTearDown(t.view.reset);
}

void main() {
  testWidgets('el resultado se dibuja en notacion matematica y muestra el paso a paso del motor', (t) async {
    await _big(t);
    final r = EngineResponse({
      ...okResponse('x = 2, x = 3'),
      'latex': {'input': r'x^{2} - 5 x + 6 = 0', 'result': r'x = 2,\quad x = 3'},
      'steps': [
        {'text': 'Ecuación original', 'latex': r'x^{2} - 5 x + 6 = 0'},
        {'text': 'Discriminante Δ = b² − 4ac', 'latex': r'\Delta = \left(-5\right)^{2} - 4\cdot 1\cdot 6 = 1'},
        {'text': 'Solución', 'latex': r'x = 2,\quad x = 3'},
      ],
    });
    await t.pumpWidget(MaterialApp(home: Scaffold(body: SingleChildScrollView(child: ResultView(response: r)))));
    await t.pumpAndSettle();
    expect(find.byKey(const Key('latex_resultado')), findsOneWidget);
    expect(find.byType(Math), findsWidgets);
    expect(find.text('Procedimiento paso a paso'), findsOneWidget);
    expect(find.text('2. Discriminante Δ = b² − 4ac'), findsOneWidget); // panel abierto por defecto cuando hay pasos
    expect(find.text('x = 2, x = 3'), findsOneWidget); // el texto exacto sigue visible y copiable
  });

  testWidgets('un LaTeX invalido no oculta el resultado (se muestra el texto)', (t) async {
    final r = EngineResponse({...okResponse('x + 1'), 'latex': {'result': r'\frac{'}});
    await t.pumpWidget(MaterialApp(home: Scaffold(body: ResultView(response: r))));
    await t.pumpAndSettle();
    expect(find.text('x + 1'), findsWidgets);
  });

  testWidgets('autovalores y estadistica se presentan como datos estructurados', (t) async {
    await _big(t);
    final eig = EngineResponse({
      ...okResponse('λ = 1 ... | λ = 3 ...'),
      'data': {
        'eigenvalues': [
          {'value': '1', 'multiplicity': 1, 'vectors': [['-1', '1']]},
          {'value': '3', 'multiplicity': 1, 'vectors': [['1', '1']]},
        ],
        'diagonalizable': true,
      }
    });
    await t.pumpWidget(MaterialApp(home: Scaffold(body: SingleChildScrollView(child: ResultView(response: eig)))));
    expect(find.text('λ = 3  (mult. 1)'), findsOneWidget);
    expect(find.text('autovector(es): (1, 1)'), findsOneWidget);
  });

  testWidgets('instruccion en espanol: se interpreta, se muestra y solo se calcula al confirmar', (t) async {
    await _big(t);
    final eng = FakeEngine((req) {
      if (req['operation'] == 'interpret') {
        return {
          ...okResponse(''),
          'exact_result': null,
          'data': {'understood': true, 'operation': 'differentiate', 'expression': 'x^3 * sin(x)', 'variables': [], 'summary': 'Derivar: x^3 * sin(x)'}
        };
      }
      return okResponse('resultado:${req['operation']}');
    });
    await t.pumpWidget(MathUniverseApp(engine: eng, store: MemoryHistoryStore()));
    await t.pumpAndSettle();
    await t.tap(find.text('Calculadora'));
    await t.pumpAndSettle();
    await t.enterText(find.byKey(const Key('campo_expresion')), 'deriva x al cubo por seno de x');
    await t.pump();
    await t.tap(find.byKey(const Key('boton_calcular')));
    await t.pumpAndSettle();
    expect(find.textContaining('Entendí: Derivar'), findsOneWidget);
    expect(eng.received.where((r) => r['operation'] == 'differentiate'), isEmpty, reason: 'no se calcula sin confirmar');
    await t.tap(find.byKey(const Key('boton_confirmar_interpretacion')));
    await t.pumpAndSettle();
    expect(eng.lastCalc['operation'], 'differentiate');
    expect(eng.lastCalc['expression'], 'x^3 * sin(x)');
    expect(eng.lastCalc['steps'], true);
    expect(eng.lastCalc['latex'], true);
  });

  testWidgets('categorias: al elegir una herramienta avanzada se envian sus campos contextuales', (t) async {
    await _big(t);
    final eng = FakeEngine((req) => okResponse('ok'));
    await t.pumpWidget(MathUniverseApp(engine: eng, store: MemoryHistoryStore()));
    await t.pumpAndSettle();
    await t.tap(find.text('Calculadora'));
    await t.pumpAndSettle();
    await t.ensureVisible(find.byKey(const Key('cat_Ecuaciones diferenciales')));
    await t.pumpAndSettle();
    await t.tap(find.byKey(const Key('cat_Ecuaciones diferenciales')));
    await t.pumpAndSettle();
    expect(find.byKey(const Key('campo_condiciones')), findsOneWidget);
    await t.enterText(find.byKey(const Key('campo_condiciones')), "y(0)=0; y'(0)=1");
    await t.tap(find.byKey(const Key('boton_calcular')));
    await t.pumpAndSettle();
    expect(eng.lastCalc['operation'], 'ode');
    expect(eng.lastCalc['expression'], "y''+y=0");
    expect(eng.lastCalc['conditions'], ['y(0)=0', "y'(0)=1"]);
  });

  test('busqueda de herramientas sin tildes ni mayusculas', () {
    expect(searchOps('autovalores').map((o) => o.id), isEmpty); // estan en Matrices, no en la calculadora
    expect(searchOps('LAPLACE').map((o) => o.id), containsAll(['laplace', 'inverse_laplace']));
    expect(searchOps('desviacion').single.id, 'stats');
    expect(searchOps('derivada').map((o) => o.id), contains('differentiate'));
  });

  test('sugerencia automatica de operacion', () {
    expect(suggestOperation('x^2-5*x+6>0'), 'inequality');
    expect(suggestOperation("y''+y=0"), 'ode');
    expect(suggestOperation('x^2=4'), 'solve');
    expect(suggestOperation('sqrt(8)'), 'evaluate');
    expect(looksLikeNaturalLanguage('deriva x^2'), isTrue);
    expect(looksLikeNaturalLanguage('x^2+1'), isFalse);
  });

  testWidgets('graficas: el motor calcula los puntos y el lienzo respeta los cortes en asintotas', (t) async {
    await _big(t);
    final eng = FakeEngine((req) => {
          ...okResponse(''),
          'exact_result': null,
          'data': {
            'kind': 'plot',
            'x_range': [-2, 2],
            'y_range': [-5, 5],
            'series': [
              {
                'expression': '1/x',
                'segments': [
                  [[-2, -0.5], [-1, -1], [-0.5, -2]],
                  [[0.5, 2], [1, 1], [2, 0.5]],
                ],
                'roots': [],
                'extrema': []
              }
            ]
          }
        });
    await t.pumpWidget(MaterialApp(home: Scaffold(body: GraphPage(engine: eng))));
    await t.pumpAndSettle();
    expect(eng.received.first['operation'], 'plot');
    expect(find.byKey(const Key('lienzo_grafica')), findsOneWidget);
    final painter = t.widget<CustomPaint>(find.byKey(const Key('lienzo_grafica'))).painter as PlotPainter;
    expect((painter.data!['series'] as List).first['segments'], hasLength(2));
    // modo 3D pide una superficie al motor
    await t.tap(find.text('3D'));
    await t.pumpAndSettle();
    expect(eng.received.last['operation'], 'plot3d');
  });

  test('pasos de la cuadricula de la grafica son "redondos"', () {
    expect(PlotPainter.niceStep(20), 5); // 20/8 = 2,5 → 5
    expect(PlotPainter.niceStep(1), 0.2);
    expect(PlotPainter.niceStep(1000), 200);
  });

  testWidgets('ingenieria: formula de la biblioteca del motor, incognita y datos', (t) async {
    await _big(t);
    final eng = FakeEngine((req) {
      if (req['operation'] == 'formulas') {
        return {
          ...okResponse(''),
          'exact_result': null,
          'data': {
            'formulas': [
              {'id': 'ohm', 'name': 'Ley de Ohm', 'equation': 'V = I*R', 'variables': {'V': 'tensión (V)', 'I': 'corriente (A)', 'R': 'resistencia (Ω)'}}
            ]
          }
        };
      }
      return okResponse('I = 3');
    });
    await t.pumpWidget(MaterialApp(home: Scaffold(body: EngineeringPage(engine: eng, store: MemoryHistoryStore()))));
    await t.pumpAndSettle();
    await t.tap(find.byKey(const Key('incognita_I')));
    await t.pump();
    await t.enterText(find.byKey(const Key('dato_V')), '12');
    await t.enterText(find.byKey(const Key('dato_R')), '4');
    await t.tap(find.byKey(const Key('boton_formula')));
    await t.pumpAndSettle();
    final sent = eng.received.last;
    expect(sent['operation'], 'formula');
    expect(sent['params'], {'id': 'ohm', 'known': {'V': '12', 'R': '4'}, 'unknown': 'I'});
    expect(find.text('I = 3'), findsOneWidget);
  });
}
