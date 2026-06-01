import '../contracts/agent_session.dart';
import '../contracts/dag_status.dart';
import '../contracts/dag_task.dart';

class MockData {
  static List<AgentSession> initialSessions() {
    return <AgentSession>[
      AgentSession(
        id: 'session-bootstrap',
        title: '桌面客户端规划',
        preview: '欢迎使用 Flutter 客户端壳。',
        lastUpdated: DateTime(2026, 4, 29, 10, 0),
      ),
    ];
  }

  static DagStatus complexDagStatus({
    List<String> pending = const <String>[],
    List<String> running = const <String>[],
    List<String> completed = const <String>[],
  }) {
    const tasks = <String, DagTask>{
      'task-1': DagTask(
        id: 'task-1',
        instruction: '梳理客户端需求与会话结构',
        dependencies: <String>[],
      ),
      'task-2': DagTask(
        id: 'task-2',
        instruction: '生成桌面布局与状态机设计',
        dependencies: <String>['task-1'],
      ),
      'task-3': DagTask(
        id: 'task-3',
        instruction: '执行高危命令前请求授权',
        dependencies: <String>['task-2'],
      ),
    };

    return DagStatus(
      pending: pending,
      running: running,
      completed: completed,
      tasks: tasks,
    );
  }
}
