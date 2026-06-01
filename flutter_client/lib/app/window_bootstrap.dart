import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:window_manager/window_manager.dart';

import 'package:flutter_client/app/window_role.dart';
import 'package:flutter_client/features/main_window/application/main_window_controller.dart';

final appWindowLaunchContextProvider =
    Provider<AppWindowLaunchContext>((ref) => const AppWindowLaunchContext());

final mainWindowControllerProvider =
    ChangeNotifierProvider<MainWindowController>((ref) {
  final controller = MainWindowController();
  ref.onDispose(controller.dispose);
  return controller;
});

class AppWindowBootstrap extends ConsumerStatefulWidget {
  const AppWindowBootstrap({super.key, required this.child});

  final Widget child;

  @override
  ConsumerState<AppWindowBootstrap> createState() => _AppWindowBootstrapState();
}

class _AppWindowBootstrapState extends ConsumerState<AppWindowBootstrap>
    with WindowListener {
  MainWindowController? _controller;

  @override
  void initState() {
    super.initState();
    windowManager.addListener(this);
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      final context = ref.read(appWindowLaunchContextProvider);
      if (context.role != AppWindowRole.main) {
        return;
      }
      _controller = ref.read(mainWindowControllerProvider);
      await _controller!.initialize();
    });
  }

  @override
  void dispose() {
    windowManager.removeListener(this);
    super.dispose();
  }

  @override
  Future<void> onWindowClose() async {
    await _controller?.handleCloseRequested();
  }

  @override
  Widget build(BuildContext context) {
    return widget.child;
  }
}
