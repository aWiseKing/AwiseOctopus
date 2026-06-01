import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_client/features/chat/presentation/chat_page.dart';

void main() {
  testWidgets('renders desktop workspace regions', (tester) async {
    await tester.pumpWidget(
      const ProviderScope(
        child: MaterialApp(
          home: ChatPage(),
        ),
      ),
    );

    await tester.pump();

    expect(find.text('会话'), findsOneWidget);
    expect(find.text('Agent 日志'), findsOneWidget);
    expect(find.text('DAG 面板'), findsOneWidget);
  });
}
