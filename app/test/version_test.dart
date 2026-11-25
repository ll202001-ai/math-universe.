import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:math_universe_app/version.dart';

void main() {
  test('la version del producto es la misma en la app, pubspec.yaml y el instalador', () {
    final pub = File('pubspec.yaml').readAsStringSync();
    expect(RegExp(r'^version: (\S+)\+\d+$', multiLine: true).firstMatch(pub)!.group(1), appVersion);
    final iss = File('../installer/MathUniverse.iss').readAsStringSync();
    expect(RegExp(r'^AppVersion=(\S+)$', multiLine: true).firstMatch(iss)!.group(1), appVersion);
  });
}
