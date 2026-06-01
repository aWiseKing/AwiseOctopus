import 'package:flutter/material.dart';

class MessageInputBar extends StatefulWidget {
  const MessageInputBar({
    super.key,
    required this.onSubmit,
    required this.hintText,
    required this.busy,
  });

  final ValueChanged<String> onSubmit;
  final String hintText;
  final bool busy;

  @override
  State<MessageInputBar> createState() => _MessageInputBarState();
}

class _MessageInputBarState extends State<MessageInputBar> {
  late final TextEditingController _controller;

  @override
  void initState() {
    super.initState();
    _controller = TextEditingController();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _submit() {
    final text = _controller.text.trim();
    if (text.isEmpty || widget.busy) {
      return;
    }
    _controller.clear();
    widget.onSubmit(text);
  }

  @override
  Widget build(BuildContext context) {
    return Row(
      children: <Widget>[
        Expanded(
          child: TextField(
            controller: _controller,
            enabled: !widget.busy,
            minLines: 1,
            maxLines: 4,
            onSubmitted: (_) => _submit(),
            decoration: InputDecoration(
              hintText: widget.hintText,
              border: const OutlineInputBorder(),
            ),
          ),
        ),
        const SizedBox(width: 12),
        FilledButton(
          onPressed: widget.busy ? null : _submit,
          child: const Text('发送'),
        ),
      ],
    );
  }
}
