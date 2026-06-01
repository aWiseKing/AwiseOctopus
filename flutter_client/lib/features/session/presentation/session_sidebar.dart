import 'package:flutter/material.dart';

import '../../../app/theme.dart';
import '../../../core/contracts/agent_session.dart';

class SessionSidebar extends StatelessWidget {
  const SessionSidebar({
    super.key,
    required this.sessions,
    required this.currentSessionId,
    required this.onSelect,
    required this.onCreateSession,
    required this.onOpenSettings,
  });

  final List<AgentSession> sessions;
  final String? currentSessionId;
  final ValueChanged<String> onSelect;
  final VoidCallback onCreateSession;
  final VoidCallback onOpenSettings;

  @override
  Widget build(BuildContext context) {
    return LiquidGlassPanel(
      padding: const EdgeInsets.all(16),
      borderRadius: 18,
      blurSigma: 22,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Text('会话', style: Theme.of(context).textTheme.titleMedium),
              const Spacer(),
              IconButton(
                tooltip: '设置',
                onPressed: onOpenSettings,
                icon: const Icon(Icons.settings_outlined),
              ),
            ],
          ),
          const SizedBox(height: 8),
          FilledButton.icon(
            onPressed: onCreateSession,
            icon: const Icon(Icons.add),
            label: const Text('新建会话'),
          ),
          const SizedBox(height: 12),
          Expanded(
            child: sessions.isEmpty
                ? const Center(child: Text('暂无会话'))
                : ListView.separated(
                    itemCount: sessions.length,
                    separatorBuilder: (_, __) => const SizedBox(height: 8),
                    itemBuilder: (context, index) {
                      final session = sessions[index];
                      final selected = session.id == currentSessionId;
                      return Material(
                        color: selected
                            ? Colors.white.withValues(alpha: 0.10)
                            : Colors.transparent,
                        borderRadius: BorderRadius.circular(12),
                        child: ListTile(
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(12),
                          ),
                          title: Text(session.title),
                          subtitle: Text(
                            session.preview.isEmpty ? '暂无预览' : session.preview,
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                          ),
                          onTap: () => onSelect(session.id),
                        ),
                      );
                    },
                  ),
          ),
        ],
      ),
    );
  }
}
