import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:tray_manager/tray_manager.dart';
import 'package:window_manager/window_manager.dart';

import 'package:flutter_client/features/main_window/application/main_window_state.dart';

abstract class MainWindowPlatformService {
  Future<void> setPreventClose(bool preventClose);

  Future<void> hide();

  Future<void> showAndFocus();

  Future<void> destroy();
}

abstract class MainWindowTrayService {
  Future<void> ensureInitialized({
    required Future<void> Function() onShowWindow,
    required Future<void> Function() onExitApplication,
  });

  Future<void> destroy();
}

abstract class MainWindowAgentApiService {
  Future<void> ensureStarted();

  Future<void> stop();
}

class MainWindowController extends ChangeNotifier {
  MainWindowController({
    MainWindowPlatformService? platformService,
    MainWindowTrayService? trayService,
    MainWindowAgentApiService? agentApiService,
    Future<void> Function()? onBeforeExit,
  })  : _platformService =
            platformService ?? const _WindowManagerPlatformService(),
        _trayService = trayService ?? _TrayManagerService(),
        _agentApiService = agentApiService ?? const _NoopAgentApiService(),
        _onBeforeExit = onBeforeExit,
        super();

  static const String closeBehaviorKey = 'main_window_close_behavior';

  final MainWindowPlatformService _platformService;
  final MainWindowTrayService _trayService;
  final MainWindowAgentApiService _agentApiService;
  final Future<void> Function()? _onBeforeExit;

  MainWindowState _state = const MainWindowState();

  MainWindowState get state => _state;

  Future<void> initialize() async {
    final prefs = await SharedPreferences.getInstance();
    final closeBehavior =
        _parseCloseBehavior(prefs.getString(closeBehaviorKey));

    _state = _state.copyWith(
      closeBehavior: closeBehavior,
      initialized: true,
    );
    notifyListeners();

    await _platformService.setPreventClose(true);
    await _syncTrayForCloseBehavior(closeBehavior);
    await _agentApiService.ensureStarted();
  }

  Future<void> setCloseBehavior(MainWindowCloseBehavior closeBehavior) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(closeBehaviorKey, closeBehavior.name);

    _state = _state.copyWith(closeBehavior: closeBehavior);
    notifyListeners();

    await _syncTrayForCloseBehavior(closeBehavior);
  }

  Future<void> handleCloseRequested() async {
    if (_state.closeBehavior == MainWindowCloseBehavior.minimizeToTray) {
      await _platformService.hide();
      return;
    }

    await _trayService.destroy();
    await _agentApiService.stop();
    await _onBeforeExit?.call();
    await _platformService.setPreventClose(false);
    await _platformService.destroy();
  }

  Future<void> _syncTrayForCloseBehavior(
    MainWindowCloseBehavior closeBehavior,
  ) async {
    if (closeBehavior == MainWindowCloseBehavior.minimizeToTray) {
      await _trayService.ensureInitialized(
        onShowWindow: _platformService.showAndFocus,
        onExitApplication: () async {
          await setCloseBehavior(MainWindowCloseBehavior.exitApplication);
          await handleCloseRequested();
        },
      );
    } else {
      await _trayService.destroy();
    }
  }

  MainWindowCloseBehavior _parseCloseBehavior(String? raw) {
    for (final behavior in MainWindowCloseBehavior.values) {
      if (behavior.name == raw) {
        return behavior;
      }
    }
    return MainWindowCloseBehavior.minimizeToTray;
  }
}

class _WindowManagerPlatformService implements MainWindowPlatformService {
  const _WindowManagerPlatformService();

  @override
  Future<void> setPreventClose(bool preventClose) {
    return windowManager.setPreventClose(preventClose);
  }

  @override
  Future<void> hide() {
    return windowManager.hide();
  }

  @override
  Future<void> showAndFocus() async {
    await windowManager.show();
    await windowManager.focus();
  }

  @override
  Future<void> destroy() {
    return windowManager.destroy();
  }
}

class _TrayManagerService with TrayListener implements MainWindowTrayService {
  bool _initialized = false;
  Future<void> Function()? _onShowWindow;
  Future<void> Function()? _onExitApplication;

  @override
  Future<void> ensureInitialized({
    required Future<void> Function() onShowWindow,
    required Future<void> Function() onExitApplication,
  }) async {
    _onShowWindow = onShowWindow;
    _onExitApplication = onExitApplication;

    if (!_initialized) {
      trayManager.addListener(this);
      _initialized = true;
    }

    await trayManager.setIcon('assets/tray/app_icon.ico');
    await trayManager.setContextMenu(
      Menu(
        items: [
          MenuItem(key: 'show_window', label: '显示主窗口'),
          MenuItem.separator(),
          MenuItem(key: 'exit_application', label: '退出'),
        ],
      ),
    );
  }

  @override
  Future<void> destroy() async {
    if (!_initialized) {
      return;
    }
    trayManager.removeListener(this);
    _initialized = false;
    await trayManager.destroy();
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
    if (menuItem.key == 'show_window') {
      _onShowWindow?.call();
    } else if (menuItem.key == 'exit_application') {
      _onExitApplication?.call();
    }
  }
}

class _NoopAgentApiService implements MainWindowAgentApiService {
  const _NoopAgentApiService();

  @override
  Future<void> ensureStarted() async {}

  @override
  Future<void> stop() async {}
}
