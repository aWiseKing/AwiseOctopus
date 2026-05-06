import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:flutter_client/app/bootstrap.dart';
import 'package:flutter_client/app/window_bootstrap.dart';
import 'package:flutter_client/app/window_role.dart';

void main() {
  testWidgets('app bootstrap renders desktop client shell', (
    WidgetTester tester,
  ) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: <Override>[
          appWindowLaunchContextProvider.overrideWithValue(
            const AppWindowLaunchContext(
              role: AppWindowRole.main,
              autostart: false,
            ),
          ),
        ],
        child: const AppBootstrap(),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('会话'), findsOneWidget);
    expect(find.text('Agent 日志'), findsOneWidget);
    expect(find.text('DAG 面板'), findsOneWidget);
  });
}
