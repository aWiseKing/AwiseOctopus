class DagTask {
  const DagTask({
    required this.id,
    required this.instruction,
    required this.dependencies,
  });

  final String id;
  final String instruction;
  final List<String> dependencies;

  factory DagTask.fromJson(Map<String, dynamic> json) {
    return DagTask(
      id: json['id'] as String,
      instruction: json['instruction'] as String? ?? '',
      dependencies: List<String>.from(json['dependencies'] as List? ?? const <String>[]),
    );
  }

  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'id': id,
      'instruction': instruction,
      'dependencies': dependencies,
    };
  }
}
