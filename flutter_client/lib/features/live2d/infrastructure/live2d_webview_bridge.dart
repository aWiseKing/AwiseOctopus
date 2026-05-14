import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';

class Live2dWebviewBridge {
  void Function(String script)? _evaluateJavascript;
  final _messageController = StreamController<Map<String, dynamic>>.broadcast();

  Stream<Map<String, dynamic>> get messages => _messageController.stream;

  void attach(void Function(String script) evaluateJavascript) {
    _evaluateJavascript = evaluateJavascript;
  }

  void detach() {
    _evaluateJavascript = null;
  }

  void handleMessage(String message) {
    try {
      final decoded = jsonDecode(message);
      if (decoded is Map<String, dynamic>) {
        _messageController.add(decoded);
      }
    } catch (e) {
      debugPrint('Live2D Bridge: failed to parse message: $e');
    }
  }

  Future<void> playRandomMotion() async {
    _evaluateJavascript?.call(
      'window.live2dDesktopPet && window.live2dDesktopPet.playRandomMotion()',
    );
  }

  Future<void> playMotion(String motionGroup) async {
    _evaluateJavascript?.call(
      'window.live2dDesktopPet && window.live2dDesktopPet.playMotion("$motionGroup")',
    );
  }

  Future<void> setScale(double scale) async {
    _evaluateJavascript?.call(
      'window.live2dDesktopPet && window.live2dDesktopPet.setScale($scale)',
    );
  }

  void dispose() {
    _messageController.close();
    _evaluateJavascript = null;
  }
}
