import 'package:flutter/material.dart';
import 'package:screen_retriever/screen_retriever.dart';
import 'package:window_manager/window_manager.dart';

class DesktopWindowConfigurator {
  DesktopWindowConfigurator._();

  static Future<void> configureMainWindow() async {
    await windowManager.ensureInitialized();
    await windowManager.setTitle('AwiseOctopus');
    await windowManager.setMinimumSize(const Size(1024, 680));
    await windowManager.setSize(const Size(1280, 800));
    await windowManager.center();
  }

  static Future<void> configurePetWindow() async {
    await windowManager.ensureInitialized();
    await windowManager.setTitle('Awise Pet');
    await windowManager.setSize(const Size(400, 600));
    await windowManager.setMinimumSize(const Size(300, 400));
    await windowManager.setTitleBarStyle(TitleBarStyle.hidden);
    await windowManager.setAlwaysOnTop(true);
    await windowManager.setSkipTaskbar(true);
    await windowManager.setBackgroundColor(Colors.transparent);

    final display = await screenRetriever.getPrimaryDisplay();
    final x = display.visiblePosition!.dx + display.visibleSize!.width - 420;
    final y = display.visiblePosition!.dy + display.visibleSize!.height - 640;
    await windowManager.setPosition(Offset(x, y));
  }

  static Future<void> showMainWindow() async {
    await windowManager.show();
    await windowManager.focus();
  }

  static Future<void> hideMainWindow() async {
    await windowManager.hide();
  }

  static Future<void> showPetWindow() async {
    await windowManager.show();
    await windowManager.focus();
  }

  static Future<void> hidePetWindow() async {
    await windowManager.hide();
  }
}
