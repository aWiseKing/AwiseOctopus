import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_client/core/contracts/agent_event.dart';

void main() {
  test('parses dag status event payload', () {
    final event = AgentEvent.fromJson(<String, dynamic>{
      'type': 'dag_status',
      'dagStatus': <String, dynamic>{
        'pending': <String>['task-2'],
        'running': <String>['task-1'],
        'completed': <String>[],
        'tasks': <String, dynamic>{
          'task-1': <String, dynamic>{
            'id': 'task-1',
            'instruction': '搜索结构',
            'dependencies': <String>[],
          },
        },
      },
    });

    expect(event.type, AgentEventType.dagStatus);
    expect(event.dagStatus?.running, contains('task-1'));
  });
}
