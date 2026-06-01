import 'package:flutter/material.dart';

import '../../../core/contracts/agent_message.dart';

class MessageList extends StatelessWidget {
  const MessageList({super.key, required this.messages});

  final List<AgentMessage> messages;

  Color _bubbleColor(BuildContext context, AgentMessage message) {
    if (message.role == AgentMessageRole.user) {
      return Theme.of(context).colorScheme.primaryContainer;
    }
    switch (message.kind) {
      case AgentMessageKind.askUser:
        return Colors.orange.shade50;
      case AgentMessageKind.dagResult:
        return Colors.blue.shade50;
      case AgentMessageKind.finalAnswer:
        return Colors.green.shade50;
      case AgentMessageKind.summary:
      case AgentMessageKind.text:
        return Colors.white;
    }
  }

  String _title(AgentMessage message) {
    if (message.role == AgentMessageRole.user) {
      return 'User';
    }
    switch (message.kind) {
      case AgentMessageKind.askUser:
        return 'Agent 求助';
      case AgentMessageKind.dagResult:
        return 'DAG 结果';
      case AgentMessageKind.finalAnswer:
        return '最终答案';
      case AgentMessageKind.summary:
        return '总结';
      case AgentMessageKind.text:
        return 'Assistant';
    }
  }

  @override
  Widget build(BuildContext context) {
    return ListView.separated(
      padding: const EdgeInsets.all(16),
      itemCount: messages.length,
      separatorBuilder: (_, __) => const SizedBox(height: 12),
      itemBuilder: (context, index) {
        final message = messages[index];
        return Align(
          alignment: message.role == AgentMessageRole.user
              ? Alignment.centerRight
              : Alignment.centerLeft,
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 720),
            child: Card(
              color: _bubbleColor(context, message),
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    Text(
                      _title(message),
                      style: Theme.of(context).textTheme.labelLarge,
                    ),
                    const SizedBox(height: 8),
                    SelectableText(message.content),
                  ],
                ),
              ),
            ),
          ),
        );
      },
    );
  }
}
