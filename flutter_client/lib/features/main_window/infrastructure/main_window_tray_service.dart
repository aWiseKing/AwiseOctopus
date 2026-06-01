import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:tray_manager/tray_manager.dart';

import '../application/main_window_controller.dart';

class TrayManagerMainWindowTrayService
    with TrayListener
    implements MainWindowTrayService {
  static const String _showWindowKey = 'show_window';
  static const String _exitApplicationKey = 'exit_application';

  bool _initialized = false;
  Future<void> Function()? _onShowWindow;
  Future<void> Function()? _onExitApplication;

  bool get _supportsTray {
    if (kIsWeb) {
      return false;
    }
    return Platform.isWindows;
  }

  @override
  Future<void> ensureInitialized({
    required Future<void> Function() onShowWindow,
    required Future<void> Function() onExitApplication,
  }) async {
    _onShowWindow = onShowWindow;
    _onExitApplication = onExitApplication;
    if (!_supportsTray || _initialized) {
      return;
    }
    trayManager.addListener(this);
    await trayManager.setIcon('assets/tray/app_icon.ico');
    await trayManager.setToolTip('AwiseOctopus');
    await trayManager.setContextMenu(
      Menu(
        items: <MenuItem>[
          MenuItem(key: _showWindowKey, label: '打开主窗口'),
          MenuItem.separator(),
          MenuItem(key: _exitApplicationKey, label: '退出程序'),
        ],
      ),
    );
    _initialized = true;
  }

  @override
  Future<void> destroy() async {
    if (!_initialized) {
      return;
    }
    trayManager.removeListener(this);
    await trayManager.destroy();
    _initialized = false;
  }

  @override
  void onTrayIconMouseDown() {
    _onShowWindow?.call();
  }

  @override
  void onTrayIconRightMouseDown() {
    trayManager.popUpContextMenu();
  }

  @override
  void onTrayMenuItemClick(MenuItem menuItem) {
    switch (menuItem.key) {
      case _showWindowKey:
        _onShowWindow?.call();
        break;
      case _exitApplicationKey:
        _onExitApplication?.call();
        break;
    }
  }
}
