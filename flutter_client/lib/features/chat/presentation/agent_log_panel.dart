import 'package:flutter/material.dart';

import '../../../app/theme.dart';

class AgentLogPanel extends StatelessWidget {
  const AgentLogPanel({super.key, required this.logs});

  final List<String> logs;

  @override
  Widget build(BuildContext context) {
    return LiquidGlassPanel(
      padding: const EdgeInsets.all(16),
      borderRadius: 18,
      blurSigma: 20,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text('Agent 日志', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 12),
          Expanded(
            child: logs.isEmpty
                ? const Center(child: Text('暂无日志'))
                : ListView.separated(
                    itemCount: logs.length,
                    separatorBuilder: (_, __) => const Divider(height: 12),
                    itemBuilder: (context, index) {
                      return SelectableText(logs[index]);
                    },
                  ),
          ),
        ],
      ),
    );
  }
}
