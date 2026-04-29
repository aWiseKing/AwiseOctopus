import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_client/core/contracts/approval_request.dart';
import 'package:flutter_client/features/approval/presentation/approval_dialog.dart';

void main() {
  testWidgets('shows fixed approval options', (tester) async {
    ApprovalDecision? selected;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ApprovalDialog(
            request: const ApprovalRequest(
              id: 'a1',
              toolName: 'shell_command',
              args: <String, dynamic>{'command': 'Remove-Item build -Recurse'},
              isDeleteOperation: true,
              sessionChoiceEnabled: false,
            ),
            onDecision: (decision) => selected = decision,
          ),
        ),
      ),
    );

    expect(find.text('only'), findsOneWidget);
    expect(find.text('no'), findsOneWidget);
    expect(find.text('session'), findsNothing);

    await tester.tap(find.text('only'));
    await tester.pumpAndSettle();

    expect(selected, ApprovalDecision.only);
  });
}
