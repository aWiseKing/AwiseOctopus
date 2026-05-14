import 'dart:async';
import 'dart:io';

import 'package:desktop_multi_window/desktop_multi_window.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:screen_retriever/screen_retriever.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:window_manager/window_manager.dart';

import 'package:flutter_client/features/live2d/application/live2d_pet_state.dart';
import 'package:flutter_client/features/live2d/infrastructure/auto_launch_service.dart';
import 'package:flutter_client/features/live2d/infrastructure/live2d_webview_bridge.dart';
import 'package:flutter_client/features/live2d/infrastructure/window_channel.dart';

typedef GetAllSubWindowIds = Future<List<int>> Function();
typedef CreatePetWindow = Future<WindowController> Function(String arguments);
typedef WindowIdAction = Future<void> Function(int windowId);
typedef NotifyPetWindowHidden = Future<void> Function();
typedef GetPrimaryDisplay = Future<Display> Function();

class Live2dPetController extends ValueNotifier<Live2dPetState> {
  Live2dPetController({
    GetAllSubWindowIds? getAllSubWindowIds,
    CreatePetWindow? createWindow,
    WindowIdAction? showWindow,
    WindowIdAction? hideWindow,
    NotifyPetWindowHidden? notifyPetWindowHidden,
    GetPrimaryDisplay? getPrimaryDisplay,
    bool? isDesktopPlatform,
  })  : _getAllSubWindowIds =
            getAllSubWindowIds ?? Live2dWindowChannel.getAllSubWindowIds,
        _createWindow = createWindow ?? Live2dWindowChannel.createWindow,
        _showWindow = showWindow ?? Live2dWindowChannel.showWindow,
        _hideWindow = hideWindow ?? Live2dWindowChannel.hideWindow,
        _notifyPetWindowHidden =
            notifyPetWindowHidden ?? Live2dWindowChannel.notifyPetWindowHidden,
        _getPrimaryDisplay =
            getPrimaryDisplay ?? screenRetriever.getPrimaryDisplay,
        _isDesktopPlatform = isDesktopPlatform ?? _defaultIsDesktopPlatform(),
        super(Live2dPetState.initial);

  final Live2dWebviewBridge bridge = Live2dWebviewBridge();
  final GetAllSubWindowIds _getAllSubWindowIds;
  final CreatePetWindow _createWindow;
  final WindowIdAction _showWindow;
  final WindowIdAction _hideWindow;
  final NotifyPetWindowHidden _notifyPetWindowHidden;
  final GetPrimaryDisplay _getPrimaryDisplay;
  final bool _isDesktopPlatform;
  int? _petWindowId;

  Live2dPetState get state => value;

  Future<void> initialize() async {
    final prefs = await SharedPreferences.getInstance();
    final enabled = prefs.getBool('live2d_enabled') ?? true;
    final savedX = prefs.getDouble('live2d_position_x');
    final savedY = prefs.getDouble('live2d_position_y');

    Offset? savedPosition;
    if (savedX != null && savedY != null) {
      savedPosition = Offset(savedX, savedY);
    }

    value = value.copyWith(
      enabled: enabled,
      windowPosition: savedPosition,
    );

    bridge.messages.listen(_onBridgeMessage);
  }

  Future<void> setEnabled(bool enabled) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool('live2d_enabled', enabled);
    value = value.copyWith(enabled: enabled);

    if (!enabled && value.petWindowVisible) {
      await hidePet();
    }
  }

  Future<void> showPet() async {
    await ensurePetWindowVisible();
  }

  Future<void> hidePet() async {
    await closeCurrentPetWindowOnly();
  }

  Future<void> togglePet() async {
    await togglePetWindow();
  }

  Future<void> ensurePetWindowVisible() async {
    if (!value.enabled || !_isDesktopPlatform) return;

    final existingWindowId = await _findPetWindowId();
    if (existingWindowId != null) {
      await _showWindow(existingWindowId);
      _petWindowId = existingWindowId;
      value = value.copyWith(
        petWindowVisible: true,
        statusMessage: null,
      );
      return;
    }

    const windowConfig = '{"role":"pet"}';
    final controller = await _createWindow(windowConfig);
    _petWindowId = controller.windowId;
    await controller.setTitle('Awise Pet');
    await controller.resizable(false);
    await _positionWindow(controller);
    await controller.show();
    value = value.copyWith(
      petWindowVisible: true,
      statusMessage: null,
    );
  }

  Future<void> togglePetWindow() async {
    if (value.petWindowVisible) {
      await closeCurrentPetWindowOnly();
      return;
    }
    await ensurePetWindowVisible();
  }

  Future<void> closeCurrentPetWindowOnly() async {
    await _notifyPetWindowHidden();
    final windowId = _petWindowId ?? await _findPetWindowId();
    if (windowId != null) {
      await _hideWindow(windowId);
    } else {
      await windowManager.hide();
    }
    _petWindowId = null;
    value = value.copyWith(
      petWindowVisible: false,
      statusMessage: '桌宠窗口已隐藏/关闭',
    );
  }

  Future<dynamic> handleMainWindowCallForTest(
    MethodCall call,
    int fromWindowId,
  ) {
    return _handleMainWindowCall(call, fromWindowId);
  }

  Future<dynamic> handleMainWindowCall(MethodCall call, int fromWindowId) {
    return _handleMainWindowCall(call, fromWindowId);
  }

  Future<void> openMainWindow() async {
    await WindowChannel.showMainWindow();
  }

  Future<void> playRandomMotion() async {
    await bridge.playRandomMotion();
  }

  Future<void> playMotion(String motionGroup) async {
    await bridge.playMotion(motionGroup);
  }

  Future<void> setScale(double scale) async {
    await bridge.setScale(scale);
  }

  Future<void> saveWindowPosition(Offset position) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setDouble('live2d_position_x', position.dx);
    await prefs.setDouble('live2d_position_y', position.dy);
    value = value.copyWith(windowPosition: position);
  }

  void setStatusMessage(String? status) {
    value = value.copyWith(statusMessage: status);
  }

  void _onBridgeMessage(Map<String, dynamic> message) {
    final type = message['type'] as String?;
    if (type == 'ready') {
      setStatusMessage('ready');
    } else if (type == 'error') {
      setStatusMessage('error: ${message['message']}');
    } else if (type == 'motionChanged') {
      setStatusMessage('motion: ${message['motion']}');
    }
  }

  Future<void> setAutoStartEnabled(bool enabled) async {
    await AutoLaunchService.setEnabled(enabled);
  }

  Future<bool> isAutoStartEnabled() async {
    return AutoLaunchService.isEnabled();
  }

  Future<void> resetPosition() async {
    final display = await _getPrimaryDisplay();
    final x = display.visiblePosition!.dx +
        display.visibleSize!.width -
        value.windowSize.width -
        20;
    final y = display.visiblePosition!.dy +
        display.visibleSize!.height -
        value.windowSize.height -
        40;
    await windowManager.setPosition(Offset(x, y));
    await saveWindowPosition(Offset(x, y));
  }

  Future<int?> _findPetWindowId() async {
    final ids = await _getAllSubWindowIds();
    if (_petWindowId != null && ids.contains(_petWindowId)) {
      return _petWindowId;
    }
    return ids.isEmpty ? null : ids.first;
  }

  Future<void> _positionWindow(WindowController controller) async {
    final display = await _getPrimaryDisplay();
    final x = display.visiblePosition!.dx +
        display.visibleSize!.width -
        value.windowSize.width -
        20;
    final y = display.visiblePosition!.dy +
        display.visibleSize!.height -
        value.windowSize.height -
        40;
    await controller.setFrame(
      Rect.fromLTWH(x, y, value.windowSize.width, value.windowSize.height),
    );
  }

  Future<dynamic> _handleMainWindowCall(
      MethodCall call, int fromWindowId) async {
    if (call.method == Live2dWindowChannel.petWindowHiddenMethod) {
      if (_petWindowId == null || _petWindowId == fromWindowId) {
        _petWindowId = null;
      }
      value = value.copyWith(
        petWindowVisible: false,
        statusMessage: '桌宠窗口已隐藏/关闭',
      );
    }
    return null;
  }

  static bool _defaultIsDesktopPlatform() {
    if (kIsWeb) {
      return false;
    }
    return Platform.isWindows || Platform.isMacOS || Platform.isLinux;
  }

  @override
  void dispose() {
    bridge.dispose();
    super.dispose();
  }
}
