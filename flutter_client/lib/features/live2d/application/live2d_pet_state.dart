import 'dart:ui';

import 'package:flutter_client/features/live2d/domain/live2d_window_config.dart';

class _Sentinel {
  const _Sentinel();
}

const _sentinel = _Sentinel();

class Live2dPetState {
  final bool enabled;
  final bool petWindowVisible;
  final Offset? windowPosition;
  final String? statusMessage;
  final Size windowSize;

  const Live2dPetState({
    this.enabled = true,
    this.petWindowVisible = false,
    this.windowPosition,
    this.statusMessage,
    this.windowSize = Live2dWindowConfig.defaultWindowSize,
  });

  static const Live2dPetState initial = Live2dPetState();

  Live2dPetState copyWith({
    bool? enabled,
    bool? petWindowVisible,
    Object? windowPosition = _sentinel,
    Object? statusMessage = _sentinel,
    Size? windowSize,
  }) {
    return Live2dPetState(
      enabled: enabled ?? this.enabled,
      petWindowVisible: petWindowVisible ?? this.petWindowVisible,
      windowPosition: identical(windowPosition, _sentinel)
          ? this.windowPosition
          : windowPosition as Offset?,
      statusMessage: identical(statusMessage, _sentinel)
          ? this.statusMessage
          : statusMessage as String?,
      windowSize: windowSize ?? this.windowSize,
    );
  }
}
