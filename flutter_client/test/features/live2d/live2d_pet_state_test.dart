import 'dart:ui';

import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_client/features/live2d/application/live2d_pet_state.dart';

void main() {
  test('copyWith updates selected fields and preserves nullable values', () {
    const initial = Live2dPetState.initial;

    final updated = initial.copyWith(
      enabled: false,
      petWindowVisible: true,
      windowPosition: const Offset(32, 48),
      statusMessage: 'ready',
    );

    expect(updated.enabled, isFalse);
    expect(updated.petWindowVisible, isTrue);
    expect(updated.windowPosition, const Offset(32, 48));
    expect(updated.statusMessage, 'ready');
    expect(updated.windowSize, initial.windowSize);
  });

  test('copyWith clears nullable fields when explicit null is provided', () {
    final state = Live2dPetState.initial.copyWith(
      windowPosition: const Offset(24, 24),
      statusMessage: 'loaded',
    );

    final cleared = state.copyWith(
      windowPosition: null,
      statusMessage: null,
    );

    expect(cleared.windowPosition, isNull);
    expect(cleared.statusMessage, isNull);
  });
}
