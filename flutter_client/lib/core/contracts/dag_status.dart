import 'dag_task.dart';

class DagStatus {
  const DagStatus({
    required this.pending,
    required this.running,
    required this.completed,
    required this.tasks,
  });

  final List<String> pending;
  final List<String> running;
  final List<String> completed;
  final Map<String, DagTask> tasks;

  factory DagStatus.fromJson(Map<String, dynamic> json) {
    final rawTasks = Map<String, dynamic>.from(json['tasks'] as Map? ?? <String, dynamic>{});
    return DagStatus(
      pending: List<String>.from(json['pending'] as List? ?? const <String>[]),
      running: List<String>.from(json['running'] as List? ?? const <String>[]),
      completed: List<String>.from(json['completed'] as List? ?? const <String>[]),
      tasks: rawTasks.map(
        (key, value) => MapEntry(
          key,
          DagTask.fromJson(Map<String, dynamic>.from(value as Map)),
        ),
      ),
    );
  }

  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'pending': pending,
      'running': running,
      'completed': completed,
      'tasks': tasks.map((key, value) => MapEntry(key, value.toJson())),
    };
  }
}
