import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_client/features/agent/application/client_agent_controller.dart';
import 'package:flutter_client/features/agent/application/client_agent_state.dart';
import 'package:flutter_client/core/contracts/approval_request.dart';

void main() {
  group('ClientAgentController', () {
    test('loads sessions on initialize', () async {
      final controller = ClientAgentController();
      await controller.initialize();

      expect(controller.state.sessions, isNotEmpty);
      expect(controller.state.messages, isNotEmpty);
    });

    test('enters awaiting user reply for clarification flow', () async {
      final controller = ClientAgentController();
      await controller.initialize();
      await controller.sendPrompt('需要补充平台信息');

      expect(controller.state.phase, ClientAgentPhase.awaitingUserReply);
      expect(
        controller.state.messages.any((message) => message.content.contains('请补充')),
        isTrue,
      );
    });

    test('moves through DAG and approval flow', () async {
      final controller = ClientAgentController();
      await controller.initialize();
      await controller.sendPrompt('请执行一个复杂 DAG 审批任务');

      expect(controller.state.phase, ClientAgentPhase.awaitingApproval);
      expect(controller.state.pendingApproval, isNotNull);

      await controller.submitApprovalDecision(ApprovalDecision.only);

      expect(controller.state.phase, ClientAgentPhase.completed);
      expect(controller.state.dagResult, isNotNull);
    });
  });
}
