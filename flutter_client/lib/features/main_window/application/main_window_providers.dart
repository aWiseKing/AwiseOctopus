import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/local_agent_api_service.dart';
import '../../live2d/application/live2d_pet_providers.dart';
import '../infrastructure/main_window_platform_service.dart';
import '../infrastructure/main_window_tray_service.dart';
import 'main_window_controller.dart';
import 'main_window_state.dart';

final mainWindowPlatformServiceProvider = Provider<MainWindowPlatformService>(
  (ref) => const WindowManagerMainWindowPlatformService(),
);

final mainWindowTrayServiceProvider = Provider<MainWindowTrayService>(
  (ref) => TrayManagerMainWindowTrayService(),
);

final localAgentApiServiceProvider = Provider<MainWindowAgentApiService>(
  (ref) => _LocalAgentApiMainWindowService(LocalAgentApiService()),
);

final mainWindowControllerProvider =
    StateNotifierProvider<MainWindowController, MainWindowState>((ref) {
  return MainWindowController(
    platformService: ref.watch(mainWindowPlatformServiceProvider),
    trayService: ref.watch(mainWindowTrayServiceProvider),
    agentApiService: ref.watch(localAgentApiServiceProvider),
    onBeforeExit: () {
      return ref
          .read(live2dPetControllerProvider.notifier)
          .prepareForApplicationExit();
    },
  );
});

class _LocalAgentApiMainWindowService implements MainWindowAgentApiService {
  _LocalAgentApiMainWindowService(this._service);

  final LocalAgentApiService _service;

  @override
  Future<void> ensureStarted() {
    return _service.ensureStarted();
  }

  @override
  Future<void> stop() {
    return _service.stop();
  }
}
