import 'package:flutter/material.dart';
import 'package:window_manager/window_manager.dart';

class DesktopWindowFrame extends StatelessWidget {
  const DesktopWindowFrame({
    super.key,
    required this.title,
    required this.child,
    this.leading,
    this.actions = const <Widget>[],
    this.debugForceDesktopShell = false,
  });

  final String title;
  final Widget child;
  final Widget? leading;
  final List<Widget> actions;
  final bool debugForceDesktopShell;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Theme.of(context).colorScheme.surface,
      body: Column(
        children: [
          _DesktopTitleBar(
            title: title,
            leading: leading,
            actions: actions,
            forceFallback: debugForceDesktopShell,
          ),
          Expanded(child: child),
        ],
      ),
    );
  }
}

class _DesktopTitleBar extends StatelessWidget {
  const _DesktopTitleBar({
    required this.title,
    required this.forceFallback,
    this.leading,
    this.actions = const <Widget>[],
  });

  final String title;
  final bool forceFallback;
  final Widget? leading;
  final List<Widget> actions;

  @override
  Widget build(BuildContext context) {
    final bar = Container(
      height: 44,
      padding: const EdgeInsets.symmetric(horizontal: 12),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surfaceContainerHighest,
        border: Border(
          bottom: BorderSide(color: Theme.of(context).dividerColor),
        ),
      ),
      child: Row(
        children: [
          if (leading != null) ...[
            leading!,
            const SizedBox(width: 8),
          ],
          Expanded(
            child: Text(
              title,
              overflow: TextOverflow.ellipsis,
              style: Theme.of(context).textTheme.titleSmall,
            ),
          ),
          ...actions,
        ],
      ),
    );

    if (forceFallback) {
      return bar;
    }
    return DragToMoveArea(child: bar);
  }
}
