import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import 'desktop_window_frame.dart';
import '../features/chat/presentation/chat_page.dart';
import '../features/settings/presentation/settings_page.dart';

final GoRouter appRouter = GoRouter(
  routes: <RouteBase>[
    ShellRoute(
      builder: (context, state, child) {
        return DesktopWindowFrame(
          title: 'AwiseOctopus Desktop Client',
          child: Padding(
            padding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
            child: child,
          ),
        );
      },
      routes: <RouteBase>[
        GoRoute(
          path: '/',
          builder: (context, state) => const ChatPage(),
        ),
        GoRoute(
          path: '/settings',
          builder: (context, state) => const SettingsPage(),
        ),
      ],
    ),
  ],
);
