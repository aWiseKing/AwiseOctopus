import 'package:flutter/material.dart';

class DagStatusBadges extends StatelessWidget {
  const DagStatusBadges({
    super.key,
    required this.pendingCount,
    required this.runningCount,
    required this.completedCount,
  });

  final int pendingCount;
  final int runningCount;
  final int completedCount;

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: <Widget>[
        Chip(label: Text('Pending $pendingCount')),
        Chip(
          backgroundColor: Colors.amber.shade100,
          label: Text('Running $runningCount'),
        ),
        Chip(
          backgroundColor: Colors.green.shade100,
          label: Text('Completed $completedCount'),
        ),
      ],
    );
  }
}
