import 'package:flutter/material.dart';

class ChatPage extends StatelessWidget {
  const ChatPage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Row(
        children: [
          Expanded(
            flex: 2,
            child: _buildPanel('会话', Icons.chat_bubble_outline),
          ),
          const VerticalDivider(width: 1),
          Expanded(
            flex: 3,
            child: Column(
              children: [
                Expanded(
                  child: _buildPanel('Agent 日志', Icons.terminal),
                ),
                const Divider(height: 1),
                Expanded(
                  child: _buildPanel('DAG 面板', Icons.account_tree_outlined),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildPanel(String title, IconData icon) {
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        Icon(icon, size: 32, color: Colors.white38),
        const SizedBox(height: 8),
        Text(title, style: const TextStyle(color: Colors.white54, fontSize: 14)),
      ],
    );
  }
}
