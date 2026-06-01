import 'package:flutter/material.dart';

import 'router.dart';
import 'theme.dart';

class AwiseClientApp extends StatelessWidget {
  const AwiseClientApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      title: 'AwiseOctopus Desktop Client',
      theme: buildAppTheme(),
      routerConfig: appRouter,
      debugShowCheckedModeBanner: false,
    );
  }
}
