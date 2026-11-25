import 'package:flutter/material.dart';

/// Preferencias de presentacion (tema y tamano de texto). Viven en memoria durante la sesion.
class AppSettings extends ChangeNotifier {
  ThemeMode themeMode = ThemeMode.system;
  double textScale = 1.0;

  void cycleTheme() {
    themeMode = switch (themeMode) {
      ThemeMode.system => ThemeMode.light,
      ThemeMode.light => ThemeMode.dark,
      ThemeMode.dark => ThemeMode.system,
    };
    notifyListeners();
  }

  void changeTextScale(double delta) {
    textScale = (textScale + delta).clamp(0.8, 1.6);
    notifyListeners();
  }
}
