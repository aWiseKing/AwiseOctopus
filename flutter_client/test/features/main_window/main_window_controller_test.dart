import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:flutter_client/features/main_window/application/main_window_controller.dart';
import 'package:flutter_client/features/main_window/application/main_window_state.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('MainWindowController', () {
    test('defaults to minimize to tray and initializes tray', () async {
      SharedPreferences.setMockInitialValues(<String, Object>{});
      final platform = _FakePlatformService();
      final tray = _FakeTrayService();
      final api = _FakeAgentApiService();
      final controller = MainWindowController(
        platformService: platform,
        trayService: tray,
        agentApiService: api,
      );

      await controller.initialize();

      expect(
        controller.state.closeBehavior,
        MainWindowCloseBehavior.minimizeToTray,
      );
      expect(platform.preventCloseValues, <bool>[true]);
      expect(tray.ensureInitializedCount, 1);
      expect(api.ensureStartedCount, 1);
    });

    test('loads persisted close behavior', () async {
      SharedPreferences.setMockInitialValues(<String, Object>{
        MainWindowController.closeBehaviorKey:
            MainWindowCloseBehavior.exitApplication.name,
      });
      final platform = _FakePlatformService();
      final tray = _FakeTrayService();
      final controller = MainWindowController(
        platformService: platform,
        trayService: tray,
      );

      await controller.initialize();

      expect(
        controller.state.closeBehavior,
        MainWindowCloseBehavior.exitApplication,
      );
      expect(tray.ensureInitializedCount, 0);
    });

    test('minimize to tray close hides window without exiting', () async {
      SharedPreferences.setMockInitialValues(<String, Object>{});
      final platform = _FakePlatformService();
      final tray = _FakeTrayService();
      var beforeExitCount = 0;
      final controller = MainWindowController(
        platformService: platform,
        trayService: tray,
        onBeforeExit: () async {
          beforeExitCount++;
        },
      );
      await controller.initialize();

      await controller.handleCloseRequested();

      expect(platform.hideCount, 1);
      expect(platform.destroyCount, 0);
      expect(beforeExitCount, 0);
    });

    test('exit behavior destroys tray, runs cleanup, and exits', () async {
      SharedPreferences.setMockInitialValues(<String, Object>{});
      final platform = _FakePlatformService();
      final tray = _FakeTrayService();
      final api = _FakeAgentApiService();
      var beforeExitCount = 0;
      final controller = MainWindowController(
        platformService: platform,
        trayService: tray,
        agentApiService: api,
        onBeforeExit: () async {
          beforeExitCount++;
        },
      );
      await controller.initialize();
      await controller
          .setCloseBehavior(MainWindowCloseBehavior.exitApplication);

      await controller.handleCloseRequested();

      expect(tray.destroyCount, 1);
      expect(api.stopCount, 1);
      expect(beforeExitCount, 1);
      expect(platform.preventCloseValues, <bool>[true, false]);
      expect(platform.destroyCount, 1);
    });

    test('switching close behavior persists and updates tray', () async {
      SharedPreferences.setMockInitialValues(<String, Object>{});
      final platform = _FakePlatformService();
      final tray = _FakeTrayService();
      final controller = MainWindowController(
        platformService: platform,
        trayService: tray,
      );
      await controller.initialize();

      await controller
          .setCloseBehavior(MainWindowCloseBehavior.exitApplication);
      await controller.setCloseBehavior(MainWindowCloseBehavior.minimizeToTray);
      final prefs = await SharedPreferences.getInstance();

      expect(
        prefs.getString(MainWindowController.closeBehaviorKey),
        MainWindowCloseBehavior.minimizeToTray.name,
      );
      expect(tray.destroyCount, 1);
      expect(tray.ensureInitializedCount, 2);
    });
  });
}

class _FakePlatformService implements MainWindowPlatformService {
  final List<bool> preventCloseValues = <bool>[];
  int hideCount = 0;
  int showAndFocusCount = 0;
  int destroyCount = 0;

  @override
  Future<void> setPreventClose(bool preventClose) async {
    preventCloseValues.add(preventClose);
  }

  @override
  Future<void> hide() async {
    hideCount++;
  }

  @override
  Future<void> showAndFocus() async {
    showAndFocusCount++;
  }

  @override
  Future<void> destroy() async {
    destroyCount++;
  }
}

class _FakeTrayService implements MainWindowTrayService {
  int ensureInitializedCount = 0;
  int destroyCount = 0;
  bool initialized = false;
  Future<void> Function()? onShowWindow;
  Future<void> Function()? onExitApplication;

  @override
  Future<void> ensureInitialized({
    required Future<void> Function() onShowWindow,
    required Future<void> Function() onExitApplication,
  }) async {
    ensureInitializedCount++;
    initialized = true;
    this.onShowWindow = onShowWindow;
    this.onExitApplication = onExitApplication;
  }

  @override
  Future<void> destroy() async {
    if (!initialized) {
      return;
    }
    initialized = false;
    destroyCount++;
  }
}

class _FakeAgentApiService implements MainWindowAgentApiService {
  int ensureStartedCount = 0;
  int stopCount = 0;

  @override
  Future<void> ensureStarted() async {
    ensureStartedCount++;
  }

  @override
  Future<void> stop() async {
    stopCount++;
  }
}
