import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:window_manager/window_manager.dart';

import 'package:flutter_client/app/bootstrap.dart';
import 'package:flutter_client/app/desktop_window_configurator.dart';
import 'package:flutter_client/app/window_role.dart';
import 'package:flutter_client/features/live2d/application/live2d_pet_providers.dart';
import 'package:flutter_client/features/live2d/infrastructure/auto_launch_service.dart';
import 'package:flutter_client/features/live2d/infrastructure/window_channel.dart';
import 'package:flutter_client/features/live2d/presentation/live2d_pet_window.dart';

void main(List<String> args) async {
  WidgetsFlutterBinding.ensureInitialized();

  final context = AppWindowLaunchContext.fromArgs(args);

  if (context.role == AppWindowRole.pet) {
    await _runPetWindow(context);
  } else {
    await _runMainWindow(context);
  }
}

Future<void> _runMainWindow(AppWindowLaunchContext context) async {
  await windowManager.ensureInitialized();

  WindowChannel.initMainWindowListener();

  await AutoLaunchService.init();

  final container = ProviderContainer();
  final petController = container.read(live2dPetControllerProvider);
  await petController.initialize();

  if (context.autostart) {
    await DesktopWindowConfigurator.hideMainWindow();
  } else {
    await DesktopWindowConfigurator.configureMainWindow();
  }

  runApp(
    UncontrolledProviderScope(
      container: container,
      child: const AppBootstrap(),
    ),
  );
}

Future<void> _runPetWindow(AppWindowLaunchContext context) async {
  await windowManager.ensureInitialized();
  await DesktopWindowConfigurator.configurePetWindow();

  WindowChannel.initPetWindowListener();

  final container = ProviderContainer();
  final petController = container.read(live2dPetControllerProvider);
  await petController.initialize();

  runApp(
    UncontrolledProviderScope(
      container: container,
      child: MaterialApp(
        debugShowCheckedModeBanner: false,
        theme: ThemeData(
          brightness: Brightness.dark,
          useMaterial3: true,
        ),
        home: Live2dPetWindow(controller: petController),
      ),
    ),
  );
}
