class AgentSession {
  const AgentSession({
    required this.id,
    required this.title,
    required this.preview,
    required this.lastUpdated,
  });

  final String id;
  final String title;
  final String preview;
  final DateTime lastUpdated;

  AgentSession copyWith({
    String? id,
    String? title,
    String? preview,
    DateTime? lastUpdated,
  }) {
    return AgentSession(
      id: id ?? this.id,
      title: title ?? this.title,
      preview: preview ?? this.preview,
      lastUpdated: lastUpdated ?? this.lastUpdated,
    );
  }

  factory AgentSession.fromJson(Map<String, dynamic> json) {
    return AgentSession(
      id: json['id'] as String,
      title: json['title'] as String? ?? '新会话',
      preview: json['preview'] as String? ?? '',
      lastUpdated: DateTime.parse(json['lastUpdated'] as String),
    );
  }

  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'id': id,
      'title': title,
      'preview': preview,
      'lastUpdated': lastUpdated.toIso8601String(),
    };
  }
}
