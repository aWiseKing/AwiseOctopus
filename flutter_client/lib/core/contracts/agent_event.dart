import 'package:flutter_client/core/contracts/approval_request.dart';

enum AgentEventType {
  thinkingLog,
  askUser,
  dagPlanned,
  dagStatus,
  approvalRequest,
  dagResult,
  summaryChunk,
  finalAnswer,
  error,
}

const _eventTypeJsonMap = <String, AgentEventType>{
  'thinking_log': AgentEventType.thinkingLog,
  'ask_user': AgentEventType.askUser,
  'dag_planned': AgentEventType.dagPlanned,
  'dag_status': AgentEventType.dagStatus,
  'approval_request': AgentEventType.approvalRequest,
  'dag_result': AgentEventType.dagResult,
  'summary_chunk': AgentEventType.summaryChunk,
  'final_answer': AgentEventType.finalAnswer,
  'error': AgentEventType.error,
};

class AgentEvent {
  final AgentEventType type;
  final String? text;
  final DagStatus? dagStatus;
  final List<DagTask>? tasks;
  final ApprovalRequest? approvalRequest;
  final Map<String, dynamic>? rawPayload;

  const AgentEvent({
    required this.type,
    this.text,
    this.dagStatus,
    this.tasks,
    this.approvalRequest,
    this.rawPayload,
  });

  factory AgentEvent.fromJson(Map<String, dynamic> json) {
    final typeStr =
        _eventTypeJsonMap[json['type'] as String] ?? AgentEventType.error;
    return AgentEvent(
      type: typeStr,
      text: json['text'] as String? ?? json['message'] as String?,
      dagStatus: json['dagStatus'] != null
          ? DagStatus.fromJson(json['dagStatus'] as Map<String, dynamic>)
          : null,
      tasks: json['tasks'] != null
          ? (json['tasks'] as List<dynamic>)
              .map((t) => DagTask.fromJson(t as Map<String, dynamic>))
              .toList()
          : null,
      approvalRequest: json['approvalRequest'] != null
          ? ApprovalRequest.fromJson(
              json['approvalRequest'] as Map<String, dynamic>)
          : null,
      rawPayload: json['rawPayload'] as Map<String, dynamic>?,
    );
  }
}

class DagStatus {
  final List<String> pending;
  final List<String> running;
  final List<String> completed;
  final Map<String, DagTask> tasks;

  const DagStatus({
    required this.pending,
    required this.running,
    required this.completed,
    required this.tasks,
  });

  factory DagStatus.fromJson(Map<String, dynamic> json) {
    final tasksJson = json['tasks'] as Map<String, dynamic>? ?? {};
    final tasks = <String, DagTask>{};
    for (final entry in tasksJson.entries) {
      tasks[entry.key] =
          DagTask.fromJson(entry.value as Map<String, dynamic>);
    }
    return DagStatus(
      pending: List<String>.from(json['pending'] as List? ?? []),
      running: List<String>.from(json['running'] as List? ?? []),
      completed: List<String>.from(json['completed'] as List? ?? []),
      tasks: tasks,
    );
  }
}

class DagTask {
  final String id;
  final String instruction;
  final List<String> dependencies;

  const DagTask({
    required this.id,
    required this.instruction,
    required this.dependencies,
  });

  factory DagTask.fromJson(Map<String, dynamic> json) {
    return DagTask(
      id: json['id'] as String,
      instruction: json['instruction'] as String? ?? '',
      dependencies: List<String>.from(json['dependencies'] as List? ?? []),
    );
  }
}
