import 'package:desktop_multi_window/desktop_multi_window.dart';
import 'package:window_manager/window_manager.dart';

class Live2dWindowChannel {
  Live2dWindowChannel._();

  static const String petWindowHiddenMethod = 'petWindowHidden';
  static const String showMainWindowMethod = 'showMainWindow';
  static const String focusMainWindowMethod = 'focusMainWindow';
  static const String closeWindowMethod = 'closeWindow';

  static bool _petWindowCreated = false;
  static WindowController? _petWindowController;

  static Future<List<int>> getAllSubWindowIds() {
    return DesktopMultiWindow.getAllSubWindowIds();
  }

  static Future<void> createPetWindow() async {
    if (_petWindowCreated) {
      await _showPetWindow();
      return;
    }

    const windowConfig = '{"role":"pet"}';
    final controller = await DesktopMultiWindow.createWindow(windowConfig);
    _petWindowController = controller;
    _petWindowCreated = true;
  }

  static Future<void> closePetWindow() async {
    if (_petWindowController != null) {
      await _petWindowController!.hide();
      _petWindowCreated = false;
      _petWindowController = null;
    }
  }

  static Future<WindowController> createWindow(String arguments) async {
    final controller = await DesktopMultiWindow.createWindow(arguments);
    _petWindowController = controller;
    _petWindowCreated = true;
    return controller;
  }

  static Future<void> showWindow(int windowId) async {
    await WindowController.fromWindowId(windowId).show();
  }

  static Future<void> hideWindow(int windowId) async {
    if (windowId == 0) {
      await windowManager.hide();
      return;
    }
    await WindowController.fromWindowId(windowId).hide();
  }

  static Future<void> notifyPetWindowHidden() async {
    await DesktopMultiWindow.invokeMethod(
      0,
      petWindowHiddenMethod,
      const <String, dynamic>{},
    );
  }

  static Future<void> _showPetWindow() async {
    await _petWindowController?.show();
  }

  static Future<void> showMainWindow() async {
    await DesktopMultiWindow.invokeMethod(
      0,
      showMainWindowMethod,
      const <String, dynamic>{},
    );
    await DesktopMultiWindow.invokeMethod(
      0,
      focusMainWindowMethod,
      const <String, dynamic>{},
    );
  }

  static void initMainWindowListener() {
    DesktopMultiWindow.setMethodHandler((call, fromWindowId) async {
      if (call.method == showMainWindowMethod ||
          call.method == focusMainWindowMethod) {
        final controller = WindowController.fromWindowId(0);
        await controller.show();
        await controller.setTitle('AwiseOctopus');
      } else if (call.method == petWindowHiddenMethod) {
        _petWindowCreated = false;
        _petWindowController = null;
      }
      return null;
    });
  }

  static void initPetWindowListener() {
    DesktopMultiWindow.setMethodHandler((call, fromWindowId) async {
      if (call.method == closeWindowMethod) {
        await notifyPetWindowHidden();
        await windowManager.hide();
      }
      return null;
    });
  }
}

class WindowChannel {
  WindowChannel._();

  static Future<void> createPetWindow() {
    return Live2dWindowChannel.createPetWindow();
  }

  static Future<void> closePetWindow() {
    return Live2dWindowChannel.closePetWindow();
  }

  static Future<void> showMainWindow() {
    return Live2dWindowChannel.showMainWindow();
  }

  static void initMainWindowListener() {
    Live2dWindowChannel.initMainWindowListener();
  }

  static void initPetWindowListener() {
    Live2dWindowChannel.initPetWindowListener();
  }
}
