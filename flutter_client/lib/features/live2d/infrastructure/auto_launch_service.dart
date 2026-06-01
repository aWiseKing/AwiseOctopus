import 'dart:io';

import 'package:launch_at_startup/launch_at_startup.dart';

class AutoLaunchService {
  AutoLaunchService._();

  static Future<void> init() async {
    launchAtStartup.setup(
      appName: 'AwiseOctopus',
      appPath: Platform.resolvedExecutable,
    );
  }

  static Future<void> setEnabled(bool enabled) async {
    if (enabled) {
      await launchAtStartup.enable();
    } else {
      await launchAtStartup.disable();
    }
  }

  static Future<bool> isEnabled() async {
    return launchAtStartup.isEnabled();
  }
}
