import 'package:flutter/material.dart';
import 'package:graphview/GraphView.dart';

import '../../../app/theme.dart';
import '../../../core/contracts/dag_status.dart';
import 'dag_status_badges.dart';

class DagPanel extends StatelessWidget {
  const DagPanel({
    super.key,
    required this.dagStatus,
    required this.rawResult,
  });

  final DagStatus? dagStatus;
  final Map<String, dynamic>? rawResult;

  Color _nodeColor(String taskId, DagStatus status) {
    if (status.completed.contains(taskId)) {
      return Colors.green.shade200;
    }
    if (status.running.contains(taskId)) {
      return Colors.amber.shade200;
    }
    return Colors.grey.shade300;
  }

  @override
  Widget build(BuildContext context) {
    final status = dagStatus;
    return LiquidGlassPanel(
      padding: const EdgeInsets.all(16),
      borderRadius: 18,
      blurSigma: 20,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text('DAG 面板', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 12),
          if (status == null)
            const Expanded(child: Center(child: Text('暂无 DAG 数据')))
          else ...<Widget>[
            DagStatusBadges(
              pendingCount: status.pending.length,
              runningCount: status.running.length,
              completedCount: status.completed.length,
            ),
            const SizedBox(height: 12),
            Expanded(
              child: Row(
                children: <Widget>[
                  Expanded(
                    flex: 3,
                    child: _DagGraphView(
                      status: status,
                      nodeColorFor: (taskId) => _nodeColor(taskId, status),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    flex: 2,
                    child: LiquidGlassPanel(
                      padding: const EdgeInsets.all(12),
                      borderRadius: 14,
                      blurSigma: 16,
                      child: SingleChildScrollView(
                        child: SelectableText(
                          rawResult == null
                              ? '暂无 DAG 执行结果'
                              : rawResult.toString(),
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _DagGraphView extends StatelessWidget {
  const _DagGraphView({
    required this.status,
    required this.nodeColorFor,
  });

  final DagStatus status;
  final Color Function(String taskId) nodeColorFor;

  @override
  Widget build(BuildContext context) {
    final graph = Graph()..isTree = true;
    final nodes = <String, Node>{};
    for (final entry in status.tasks.entries) {
      nodes[entry.key] = Node.Id(entry.key);
      graph.addNode(nodes[entry.key]!);
    }
    for (final entry in status.tasks.entries) {
      final taskNode = nodes[entry.key]!;
      for (final dep in entry.value.dependencies) {
        final depNode = nodes[dep];
        if (depNode != null) {
          graph.addEdge(depNode, taskNode);
        }
      }
    }
    final algorithm = BuchheimWalkerAlgorithm(
      BuchheimWalkerConfiguration()
        ..orientation = BuchheimWalkerConfiguration.ORIENTATION_LEFT_RIGHT
        ..siblingSeparation = 24
        ..levelSeparation = 28
        ..subtreeSeparation = 28,
      TreeEdgeRenderer(BuchheimWalkerConfiguration()),
    );
    return InteractiveViewer(
      constrained: false,
      boundaryMargin: const EdgeInsets.all(24),
      minScale: 0.1,
      maxScale: 4.0,
      child: GraphView(
        graph: graph,
        algorithm: algorithm,
        builder: (Node node) {
          final task = status.tasks[node.key?.value];
          return Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: nodeColorFor(task!.id),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: Colors.black12),
            ),
            width: 180,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: <Widget>[
                Text(task.id, style: Theme.of(context).textTheme.labelLarge),
                const SizedBox(height: 4),
                Text(task.instruction, maxLines: 3, overflow: TextOverflow.ellipsis),
              ],
            ),
          );
        },
      ),
    );
  }
}
