import 'package:flutter_client/core/contracts/approval_request.dart';

enum ClientAgentPhase {
  idle,
  waitingForPrompt,
  awaitingUserReply,
  awaitingApproval,
  completed,
}

class ChatMessage {
  final String id;
  final String role;
  final String content;

  const ChatMessage({
    required this.id,
    required this.role,
    required this.content,
  });
}

class SessionSummary {
  final String id;
  final String title;
  final String preview;

  const SessionSummary({
    required this.id,
    required this.title,
    required this.preview,
  });
}

class ClientAgentState {
  final ClientAgentPhase phase;
  final List<SessionSummary> sessions;
  final List<ChatMessage> messages;
  final ApprovalRequest? pendingApproval;
  final Map<String, String>? dagResult;

  const ClientAgentState({
    this.phase = ClientAgentPhase.idle,
    this.sessions = const [],
    this.messages = const [],
    this.pendingApproval,
    this.dagResult,
  });

  ClientAgentState copyWith({
    ClientAgentPhase? phase,
    List<SessionSummary>? sessions,
    List<ChatMessage>? messages,
    ApprovalRequest? pendingApproval,
    bool clearPendingApproval = false,
    Map<String, String>? dagResult,
    bool clearDagResult = false,
  }) {
    return ClientAgentState(
      phase: phase ?? this.phase,
      sessions: sessions ?? this.sessions,
      messages: messages ?? this.messages,
      pendingApproval:
          clearPendingApproval ? null : (pendingApproval ?? this.pendingApproval),
      dagResult: clearDagResult ? null : (dagResult ?? this.dagResult),
    );
  }
}
