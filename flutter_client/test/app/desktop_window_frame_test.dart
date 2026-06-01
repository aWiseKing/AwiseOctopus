import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:flutter_client/app/desktop_window_frame.dart';

void main() {
  testWidgets('desktop shell fills the window without a root SafeArea', (
    tester,
  ) async {
    await tester.pumpWidget(
      const ProviderScope(
        child: MaterialApp(
          home: DesktopWindowFrame(
            title: 'Desktop Shell',
            debugForceDesktopShell: true,
            child: ColoredBox(
              color: Colors.white,
              child: SizedBox.expand(child: Text('Workspace')),
            ),
          ),
        ),
      ),
    );

    await tester.pump();

    expect(find.byType(SafeArea), findsNothing);
    expect(find.text('Desktop Shell'), findsOneWidget);
    expect(find.text('Workspace'), findsOneWidget);
  });
}
