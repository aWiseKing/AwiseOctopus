import '../contracts/agent_event.dart';
import '../contracts/agent_message.dart';
import '../contracts/agent_session.dart';
import '../contracts/approval_request.dart';

abstract class AgentApi {
  Future<List<AgentSession>> listSessions();

  Future<AgentSession> createSession();

  Future<List<AgentMessage>> loadSessionHistory(String sessionId);

  Stream<AgentEvent> sendPrompt({
    required String sessionId,
    required String prompt,
  });

  Stream<AgentEvent> replyToAskUser({
    required String sessionId,
    required String reply,
  });

  Stream<AgentEvent> submitApprovalDecision({
    required String sessionId,
    required ApprovalDecision decision,
  });
}
