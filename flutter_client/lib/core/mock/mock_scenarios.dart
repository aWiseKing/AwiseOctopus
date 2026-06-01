import '../contracts/agent_event.dart';
import '../contracts/approval_request.dart';
import '../contracts/dag_task.dart';
import 'mock_data.dart';

class MockScenarios {
  static Stream<AgentEvent> simpleAnswerFlow(String prompt) async* {
    yield* _delayed(<AgentEvent>[
      AgentEvent.thinkingLog('=== [思考Agent 启动] 开始分析任务 ==='),
      AgentEvent.thinkingLog('正在整理你的问题: $prompt'),
      AgentEvent.finalAnswer('这是一个简单回答流，后续可切换到真实 Python Agent 服务。'),
    ]);
  }

  static Stream<AgentEvent> askUserFlow(String prompt) async* {
    yield* _delayed(<AgentEvent>[
      AgentEvent.thinkingLog('=== [思考Agent 启动] 需要更多上下文 ==='),
      AgentEvent.askUser('请补充你希望优先支持的平台或场景。'),
    ]);
  }

  static Stream<AgentEvent> continueAfterAsk(String reply) async* {
    yield* _delayed(<AgentEvent>[
      AgentEvent.thinkingLog('已收到补充信息: $reply'),
      AgentEvent.finalAnswer('已根据你的补充继续规划，当前客户端壳会把这些信息写入状态机与契约层。'),
    ]);
  }

  static Stream<AgentEvent> approvalFlowStart(String prompt) async* {
    yield* _delayed(<AgentEvent>[
      AgentEvent.thinkingLog('=== [思考Agent 启动] 正在规划复杂任务 ==='),
      AgentEvent.thinkingLog('为请求 "$prompt" 生成 DAG 任务图。'),
      AgentEvent.dagPlanned(const <DagTask>[]),
      AgentEvent.dagStatusEvent(
        MockData.complexDagStatus(
          pending: const <String>['task-2', 'task-3'],
          running: const <String>['task-1'],
          completed: const <String>[],
        ),
      ),
      AgentEvent.dagStatusEvent(
        MockData.complexDagStatus(
          pending: const <String>['task-3'],
          running: const <String>['task-2'],
          completed: const <String>['task-1'],
        ),
      ),
      AgentEvent.approval(
        const ApprovalRequest(
          id: 'approval-1',
          toolName: 'shell_command',
          args: <String, dynamic>{'command': 'Remove-Item build -Recurse'},
          isDeleteOperation: true,
          sessionChoiceEnabled: false,
        ),
      ),
    ]);
  }

  static Stream<AgentEvent> continueAfterApproval(ApprovalDecision decision) async* {
    if (decision == ApprovalDecision.no) {
      yield* _delayed(<AgentEvent>[
        AgentEvent.thinkingLog('用户拒绝了高危操作，流程转入收敛。'),
        AgentEvent.summaryChunk('已保留规划结果，但中止实际高危步骤。'),
        AgentEvent.finalAnswer('任务已停止在高危确认阶段，未继续执行删除类操作。'),
      ]);
      return;
    }

    yield* _delayed(<AgentEvent>[
      AgentEvent.thinkingLog('高危操作已获授权，继续执行后续任务。'),
      AgentEvent.dagStatusEvent(
        MockData.complexDagStatus(
          pending: const <String>[],
          running: const <String>['task-3'],
          completed: const <String>['task-1', 'task-2'],
        ),
      ),
      AgentEvent.dagStatusEvent(
        MockData.complexDagStatus(
          pending: const <String>[],
          running: const <String>[],
          completed: const <String>['task-1', 'task-2', 'task-3'],
        ),
      ),
      AgentEvent.dagResult(<String, dynamic>{
        'task-1': '需求分析完成',
        'task-2': '桌面布局生成完成',
        'task-3': '审批流程验证完成',
      }),
      AgentEvent.summaryChunk('正在汇总复杂流程结果...'),
      AgentEvent.summaryChunk('DAG、审批与最终总结均已串联。'),
      AgentEvent.finalAnswer('复杂任务演示已完成，Flutter 客户端壳已具备接入真实后端的结构。'),
    ]);
  }

  static Stream<AgentEvent> _delayed(List<AgentEvent> events) async* {
    for (final event in events) {
      await Future<void>.delayed(const Duration(milliseconds: 180));
      yield event;
    }
  }
}
