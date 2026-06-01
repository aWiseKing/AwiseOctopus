import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_client/app/window_role.dart';

void main() {
  group('AppWindowLaunchContext', () {
    test('parses default main window args', () {
      final context = AppWindowLaunchContext.fromArgs(const <String>[]);

      expect(context.role, AppWindowRole.main);
      expect(context.autostart, isFalse);
      expect(context.windowId, isNull);
    });

    test('parses autostart flag for main window', () {
      final context =
          AppWindowLaunchContext.fromArgs(const <String>['--autostart']);

      expect(context.role, AppWindowRole.main);
      expect(context.autostart, isTrue);
    });

    test('parses pet window payload from desktop_multi_window', () {
      final context = AppWindowLaunchContext.fromArgs(const <String>[
        'multi_window',
        '2',
        '{"role":"pet","autostart":true}',
      ]);

      expect(context.role, AppWindowRole.pet);
      expect(context.windowId, 2);
      expect(context.autostart, isTrue);
    });
  });
}
