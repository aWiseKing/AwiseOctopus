import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:window_manager/window_manager.dart';

import '../application/main_window_controller.dart';

class WindowManagerMainWindowPlatformService
    implements MainWindowPlatformService {
  const WindowManagerMainWindowPlatformService();

  bool get _isDesktopShell {
    if (kIsWeb) {
      return false;
    }
    return Platform.isWindows || Platform.isLinux || Platform.isMacOS;
  }

  @override
  Future<void> setPreventClose(bool preventClose) async {
    if (!_isDesktopShell) {
      return;
    }
    await windowManager.setPreventClose(preventClose);
  }

  @override
  Future<void> hide() async {
    if (!_isDesktopShell) {
      return;
    }
    await windowManager.hide();
  }

  @override
  Future<void> showAndFocus() async {
    if (!_isDesktopShell) {
      return;
    }
    await windowManager.show();
    await windowManager.focus();
  }

  @override
  Future<void> destroy() async {
    if (!_isDesktopShell) {
      return;
    }
    await windowManager.destroy();
  }
}
