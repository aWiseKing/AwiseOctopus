import '../contracts/agent_event.dart';
import '../contracts/agent_message.dart';
import '../contracts/agent_session.dart';
import '../contracts/approval_request.dart';
import '../mock/mock_data.dart';
import '../mock/mock_scenarios.dart';
import 'agent_api.dart';

class MockAgentApi implements AgentApi {
  MockAgentApi() {
    _sessions = List<AgentSession>.from(MockData.initialSessions());
    _historyBySession = <String, List<AgentMessage>>{
      _sessions.first.id: <AgentMessage>[
        AgentMessage(
          id: 'bootstrap-msg-1',
          role: AgentMessageRole.assistant,
          kind: AgentMessageKind.text,
          content: '欢迎使用 AwiseOctopus Flutter 桌面客户端。',
          createdAt: DateTime(2026, 4, 29, 10, 0),
        ),
      ],
    };
  }

  late final List<AgentSession> _sessions;
  late final Map<String, List<AgentMessage>> _historyBySession;
  int _sessionCounter = 2;

  @override
  Future<AgentSession> createSession() async {
    final session = AgentSession(
      id: 'session-${_sessionCounter++}',
      title: '新会话',
      preview: '',
      lastUpdated: DateTime.now(),
    );
    _sessions.insert(0, session);
    _historyBySession[session.id] = <AgentMessage>[];
    return session;
  }

  @override
  Future<List<AgentSession>> listSessions() async {
    return List<AgentSession>.from(_sessions);
  }

  @override
  Future<List<AgentMessage>> loadSessionHistory(String sessionId) async {
    return List<AgentMessage>.from(
      _historyBySession[sessionId] ?? const <AgentMessage>[],
    );
  }

  @override
  Stream<AgentEvent> replyToAskUser({
    required String sessionId,
    required String reply,
  }) {
    return MockScenarios.continueAfterAsk(reply);
  }

  @override
  Stream<AgentEvent> sendPrompt({
    required String sessionId,
    required String prompt,
  }) {
    final lower = prompt.toLowerCase();
    if (lower.contains('复杂') || lower.contains('dag') || lower.contains('审批')) {
      return MockScenarios.approvalFlowStart(prompt);
    }
    if (lower.contains('补充') || lower.contains('澄清') || lower.contains('平台')) {
      return MockScenarios.askUserFlow(prompt);
    }
    return MockScenarios.simpleAnswerFlow(prompt);
  }

  @override
  Stream<AgentEvent> submitApprovalDecision({
    required String sessionId,
    required ApprovalDecision decision,
  }) {
    return MockScenarios.continueAfterApproval(decision);
  }

  void appendAssistantMessage(String sessionId, AgentMessage message) {
    final history = _historyBySession.putIfAbsent(
      sessionId,
      () => <AgentMessage>[],
    );
    history.add(message);
    _updateSessionPreview(sessionId, message.content);
  }

  void appendUserMessage(String sessionId, AgentMessage message) {
    final history = _historyBySession.putIfAbsent(
      sessionId,
      () => <AgentMessage>[],
    );
    history.add(message);
    _updateSessionPreview(sessionId, message.content);
  }

  void _updateSessionPreview(String sessionId, String preview) {
    final index = _sessions.indexWhere((session) => session.id == sessionId);
    if (index == -1) {
      return;
    }
    _sessions[index] = _sessions[index].copyWith(
      preview: preview,
      lastUpdated: DateTime.now(),
    );
  }
}
