import 'package:flutter_test/flutter_test.dart';
import 'package:math_universe_app/engine/models.dart';

void main() {
  test('respuesta exitosa con matriz', () {
    final r = EngineResponse({
      'status': 'success_exact',
      'exact_result': '[[1, 2], [3, 4]]',
      'verification': {'status': 'passed', 'method': 'x'},
      'data': {'matrix': [['1', '2'], ['3', '4']]},
      'conditions': ['x != 2'],
    });
    expect(r.hasResult, isTrue);
    expect(r.verificationStatus, 'passed');
    expect(r.matrix, [['1', '2'], ['3', '4']]);
    expect(r.conditions, ['x != 2']);
  });

  test('respuesta de error: no tiene resultado', () {
    final r = EngineResponse({'status': 'domain_error', 'error': {'code': 'DOMAIN_ERROR', 'message': 'singular'}});
    expect(r.hasResult, isFalse);
    expect(r.errorCode, 'DOMAIN_ERROR');
    expect(r.errorMessage, 'singular');
    expect(r.verificationStatus, 'not_performed');
    expect(r.exactResult, isNull);
  });

  test('respuesta local de cliente', () {
    final r = EngineResponse.local('timeout', 'TIMEOUT', 'x');
    expect(r.status, 'timeout');
    expect(r.hasResult, isFalse);
  });

  test('parseMatrixText acepta espacios, comas y punto y coma', () {
    expect(parseMatrixText('1 2\n3 4'), [['1', '2'], ['3', '4']]);
    expect(parseMatrixText('1,2;3,4'), [['1', '2'], ['3', '4']]);
    expect(parseMatrixText('1/2  0.25\n\n3 -4'), [['1/2', '0.25'], ['3', '-4']]);
  });

  test('parseMatrixText rechaza vacia o irregular', () {
    expect(() => parseMatrixText('  \n '), throwsFormatException);
    expect(() => parseMatrixText('1 2\n3'), throwsFormatException);
  });

  test('todas las operaciones de matrices del contrato 1.1 estan en la interfaz', () {
    expect(matrixOperations.keys.toSet(), {
      'matrix_add', 'matrix_sub', 'matrix_mul', 'matrix_transpose', 'matrix_det', 'matrix_inverse', 'matrix_rank', 'matrix_rref', 'matrix_solve',
      'eigen'
    });
    expect(matrixOpsNeedingB, {'matrix_add', 'matrix_sub', 'matrix_mul', 'matrix_solve'});
  });
}
