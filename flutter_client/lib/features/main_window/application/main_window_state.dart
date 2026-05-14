enum MainWindowCloseBehavior { minimizeToTray, exitApplication }

class MainWindowState {
  const MainWindowState({
    this.closeBehavior = MainWindowCloseBehavior.minimizeToTray,
    this.initialized = false,
  });

  final MainWindowCloseBehavior closeBehavior;
  final bool initialized;

  MainWindowState copyWith({
    MainWindowCloseBehavior? closeBehavior,
    bool? initialized,
  }) {
    return MainWindowState(
      closeBehavior: closeBehavior ?? this.closeBehavior,
      initialized: initialized ?? this.initialized,
    );
  }
}
