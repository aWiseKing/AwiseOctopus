enum AgentMessageRole { user, assistant, system }

enum AgentMessageKind { text, askUser, finalAnswer, dagResult, summary }

class AgentMessage {
  const AgentMessage({
    required this.id,
    required this.role,
    required this.kind,
    required this.content,
    required this.createdAt,
    this.metadata,
  });

  final String id;
  final AgentMessageRole role;
  final AgentMessageKind kind;
  final String content;
  final DateTime createdAt;
  final Map<String, dynamic>? metadata;

  AgentMessage copyWith({
    String? id,
    AgentMessageRole? role,
    AgentMessageKind? kind,
    String? content,
    DateTime? createdAt,
    Map<String, dynamic>? metadata,
  }) {
    return AgentMessage(
      id: id ?? this.id,
      role: role ?? this.role,
      kind: kind ?? this.kind,
      content: content ?? this.content,
      createdAt: createdAt ?? this.createdAt,
      metadata: metadata ?? this.metadata,
    );
  }

  factory AgentMessage.fromJson(Map<String, dynamic> json) {
    return AgentMessage(
      id: json['id'] as String,
      role: _roleFromString(json['role'] as String? ?? 'assistant'),
      kind: _kindFromString(json['kind'] as String? ?? 'text'),
      content: json['content'] as String? ?? '',
      createdAt: DateTime.parse(json['createdAt'] as String),
      metadata: json['metadata'] as Map<String, dynamic>?,
    );
  }

  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'id': id,
      'role': role.name,
      'kind': kind.name,
      'content': content,
      'createdAt': createdAt.toIso8601String(),
      'metadata': metadata,
    };
  }
}

AgentMessageRole _roleFromString(String value) {
  return AgentMessageRole.values.firstWhere(
    (item) => item.name == value,
    orElse: () => AgentMessageRole.assistant,
  );
}

AgentMessageKind _kindFromString(String value) {
  return AgentMessageKind.values.firstWhere(
    (item) => item.name == value,
    orElse: () => AgentMessageKind.text,
  );
}
