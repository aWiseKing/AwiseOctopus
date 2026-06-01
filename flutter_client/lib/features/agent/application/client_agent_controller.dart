import 'package:flutter/foundation.dart';

import 'package:flutter_client/features/agent/application/client_agent_state.dart';
import 'package:flutter_client/core/contracts/approval_request.dart';

class ClientAgentController {
  final _stateNotifier = ValueNotifier(const ClientAgentState());

  ClientAgentState get state => _stateNotifier.value;

  Future<void> initialize() async {
    _stateNotifier.value = const ClientAgentState(
      sessions: [
        SessionSummary(
          id: 'session-001',
          title: '部署排查',
          preview: '最近一次部署排查会话',
        ),
        SessionSummary(
          id: 'session-002',
          title: '新会话',
          preview: '',
        ),
      ],
      messages: [
        ChatMessage(
          id: 'm1',
          role: 'user',
          content: '帮我总结这个需求',
        ),
      ],
    );
  }

  Future<void> sendPrompt(String prompt) async {
    if (prompt.contains('补充')) {
      _stateNotifier.value = state.copyWith(
        phase: ClientAgentPhase.awaitingUserReply,
        messages: [
          ...state.messages,
          ChatMessage(
            id: 'm${state.messages.length + 1}',
            role: 'agent',
            content: '请补充$prompt',
          ),
        ],
      );
    } else if (prompt.contains('DAG') || prompt.contains('审批')) {
      _stateNotifier.value = state.copyWith(
        phase: ClientAgentPhase.awaitingApproval,
        pendingApproval: const ApprovalRequest(
          id: 'approval-001',
          toolName: 'shell_command',
          args: {'command': 'Remove-Item build -Recurse'},
          isDeleteOperation: true,
          sessionChoiceEnabled: false,
        ),
        messages: [
          ...state.messages,
          ChatMessage(
            id: 'm${state.messages.length + 1}',
            role: 'user',
            content: prompt,
          ),
        ],
      );
    }
  }

  Future<void> submitApprovalDecision(ApprovalDecision decision) async {
    if (decision == ApprovalDecision.only) {
      _stateNotifier.value = state.copyWith(
        phase: ClientAgentPhase.completed,
        clearPendingApproval: true,
        dagResult: const {'task-1': '完成', 'task-2': '完成'},
        messages: [
          ...state.messages,
          const ChatMessage(
            id: 'result-1',
            role: 'agent',
            content: '审批已通过，任务执行完成',
          ),
        ],
      );
    }
  }

  void dispose() {
    _stateNotifier.dispose();
  }
}
