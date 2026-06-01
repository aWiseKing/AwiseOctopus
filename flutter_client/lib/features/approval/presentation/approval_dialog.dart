import 'package:flutter/material.dart';
import 'package:flutter_client/core/contracts/approval_request.dart';

class ApprovalDialog extends StatefulWidget {
  final ApprovalRequest request;
  final void Function(ApprovalDecision decision) onDecision;

  const ApprovalDialog({
    super.key,
    required this.request,
    required this.onDecision,
  });

  @override
  State<ApprovalDialog> createState() => _ApprovalDialogState();
}

class _ApprovalDialogState extends State<ApprovalDialog> {
  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Row(
        children: [
          Icon(
            widget.request.isDeleteOperation ? Icons.warning_amber : Icons.info_outline,
            color: widget.request.isDeleteOperation ? Colors.orange : Colors.blue,
          ),
          const SizedBox(width: 8),
          const Text('工具执行确认'),
        ],
      ),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('工具: ${widget.request.toolName}'),
          const SizedBox(height: 8),
          if (widget.request.args.containsKey('command'))
            Text(
              '命令: ${widget.request.args['command']}',
              style: const TextStyle(fontFamily: 'monospace', fontSize: 12),
            ),
        ],
      ),
      actions: [
        TextButton(
          onPressed: () {
            widget.onDecision(ApprovalDecision.no);
            Navigator.of(context).pop();
          },
          child: const Text('no'),
        ),
        if (widget.request.sessionChoiceEnabled)
          TextButton(
            onPressed: () {
              widget.onDecision(ApprovalDecision.session);
              Navigator.of(context).pop();
            },
            child: const Text('session'),
          ),
        TextButton(
          onPressed: () {
            widget.onDecision(ApprovalDecision.only);
            Navigator.of(context).pop();
          },
          child: const Text('only'),
        ),
      ],
    );
  }
}
