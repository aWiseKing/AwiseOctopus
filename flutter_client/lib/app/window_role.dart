import 'dart:convert' as dart;

enum AppWindowRole { main, pet }

class AppWindowLaunchContext {
  final AppWindowRole role;
  final bool autostart;
  final int? windowId;

  const AppWindowLaunchContext({
    this.role = AppWindowRole.main,
    this.autostart = false,
    this.windowId,
  });

  factory AppWindowLaunchContext.fromArgs(List<String> args) {
    if (args.length >= 3 && args[0] == 'multi_window') {
      final id = int.tryParse(args[1]);
      final payload = _tryParseJson(args[2]);
      return AppWindowLaunchContext(
        role: payload?['role'] == 'pet' ? AppWindowRole.pet : AppWindowRole.main,
        windowId: id,
        autostart: payload?['autostart'] == true,
      );
    }

    return AppWindowLaunchContext(
      role: AppWindowRole.main,
      autostart: args.contains('--autostart'),
    );
  }

  static Map<String, dynamic>? _tryParseJson(String raw) {
    try {
      final value = dart.jsonDecode(raw);
      if (value is Map<String, dynamic>) return value;
      return null;
    } catch (_) {
      return null;
    }
  }
}
