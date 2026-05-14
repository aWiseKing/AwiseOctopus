enum ApprovalDecision {
  session,
  only,
  no,
}

class ApprovalRequest {
  final String id;
  final String toolName;
  final Map<String, dynamic> args;
  final bool isDeleteOperation;
  final bool sessionChoiceEnabled;

  const ApprovalRequest({
    required this.id,
    required this.toolName,
    required this.args,
    required this.isDeleteOperation,
    required this.sessionChoiceEnabled,
  });

  factory ApprovalRequest.fromJson(Map<String, dynamic> json) {
    return ApprovalRequest(
      id: json['id'] as String,
      toolName: json['tool_name'] as String? ?? json['toolName'] as String? ?? '',
      args: Map<String, dynamic>.from(json['args'] as Map? ?? {}),
      isDeleteOperation: json['is_delete_operation'] as bool? ??
          json['isDeleteOperation'] as bool? ??
          false,
      sessionChoiceEnabled: json['session_choice_enabled'] as bool? ??
          json['sessionChoiceEnabled'] as bool? ??
          false,
    );
  }
}
