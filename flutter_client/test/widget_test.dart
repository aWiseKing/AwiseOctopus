import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:flutter_client/app/bootstrap.dart';

void main() {
  testWidgets('app bootstrap renders desktop client shell', (
    WidgetTester tester,
  ) async {
    await tester.pumpWidget(
      const ProviderScope(
        child: AppBootstrap(),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('会话'), findsOneWidget);
    expect(find.text('Agent 日志'), findsOneWidget);
    expect(find.text('DAG 面板'), findsOneWidget);
  });
}
