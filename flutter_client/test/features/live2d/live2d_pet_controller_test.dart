import 'package:desktop_multi_window/desktop_multi_window.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_client/features/live2d/application/live2d_pet_controller.dart';
import 'package:flutter_client/features/live2d/infrastructure/window_channel.dart';
import 'package:screen_retriever/screen_retriever.dart';

void main() {
  group('Live2dPetController', () {
    test('marks pet hidden when pet window notifies main window', () async {
      final fake = _FakePetWindowPlatform(subWindowIds: <int>[7]);
      final controller = Live2dPetController(
        getAllSubWindowIds: fake.getAllSubWindowIds,
        createWindow: fake.createWindow,
        showWindow: fake.showWindow,
        hideWindow: fake.hideWindow,
        notifyPetWindowHidden: fake.notifyPetWindowHidden,
        getPrimaryDisplay: fake.getPrimaryDisplay,
        isDesktopPlatform: true,
      );

      await controller.ensurePetWindowVisible();
      expect(controller.state.petWindowVisible, isTrue);

      await controller.handleMainWindowCallForTest(
        const MethodCall(Live2dWindowChannel.petWindowHiddenMethod),
        7,
      );

      expect(controller.state.petWindowVisible, isFalse);
      expect(controller.state.statusMessage, '桌宠窗口已隐藏/关闭');
    });

    test('reuses hidden pet window when showing again', () async {
      final fake = _FakePetWindowPlatform(subWindowIds: <int>[7]);
      final controller = Live2dPetController(
        getAllSubWindowIds: fake.getAllSubWindowIds,
        createWindow: fake.createWindow,
        showWindow: fake.showWindow,
        hideWindow: fake.hideWindow,
        notifyPetWindowHidden: fake.notifyPetWindowHidden,
        getPrimaryDisplay: fake.getPrimaryDisplay,
        isDesktopPlatform: true,
      );

      await controller.handleMainWindowCallForTest(
        const MethodCall(Live2dWindowChannel.petWindowHiddenMethod),
        7,
      );
      await controller.ensurePetWindowVisible();

      expect(fake.showWindowIds, <int>[7]);
      expect(fake.createdWindows, isEmpty);
      expect(controller.state.petWindowVisible, isTrue);
    });

    test('toggle shows hidden pet window instead of hiding it again', () async {
      final fake = _FakePetWindowPlatform(subWindowIds: <int>[7]);
      final controller = Live2dPetController(
        getAllSubWindowIds: fake.getAllSubWindowIds,
        createWindow: fake.createWindow,
        showWindow: fake.showWindow,
        hideWindow: fake.hideWindow,
        notifyPetWindowHidden: fake.notifyPetWindowHidden,
        getPrimaryDisplay: fake.getPrimaryDisplay,
        isDesktopPlatform: true,
      );

      await controller.handleMainWindowCallForTest(
        const MethodCall(Live2dWindowChannel.petWindowHiddenMethod),
        7,
      );
      await controller.togglePetWindow();

      expect(fake.showWindowIds, <int>[7]);
      expect(fake.hideWindowIds, isEmpty);
      expect(controller.state.petWindowVisible, isTrue);
    });

    test('creates pet window when no hidden window exists', () async {
      final fake = _FakePetWindowPlatform(subWindowIds: <int>[]);
      final controller = Live2dPetController(
        getAllSubWindowIds: fake.getAllSubWindowIds,
        createWindow: fake.createWindow,
        showWindow: fake.showWindow,
        hideWindow: fake.hideWindow,
        notifyPetWindowHidden: fake.notifyPetWindowHidden,
        getPrimaryDisplay: fake.getPrimaryDisplay,
        isDesktopPlatform: true,
      );

      await controller.ensurePetWindowVisible();

      expect(fake.createdWindows.single.windowId, 42);
      expect(fake.createdWindows.single.showCount, 1);
      expect(controller.state.petWindowVisible, isTrue);
    });

    test('notifies main window before hiding current pet window', () async {
      final fake = _FakePetWindowPlatform(subWindowIds: <int>[7]);
      final controller = Live2dPetController(
        getAllSubWindowIds: fake.getAllSubWindowIds,
        createWindow: fake.createWindow,
        showWindow: fake.showWindow,
        hideWindow: fake.hideWindow,
        notifyPetWindowHidden: fake.notifyPetWindowHidden,
        getPrimaryDisplay: fake.getPrimaryDisplay,
        isDesktopPlatform: true,
      );

      await controller.ensurePetWindowVisible();
      await controller.closeCurrentPetWindowOnly();

      expect(fake.notifyHiddenCount, 1);
      expect(fake.hideWindowIds, <int>[7]);
      expect(controller.state.petWindowVisible, isFalse);
    });
  });
}

class _FakePetWindowPlatform {
  _FakePetWindowPlatform({required this.subWindowIds});

  final List<int> subWindowIds;
  final List<int> showWindowIds = <int>[];
  final List<int> hideWindowIds = <int>[];
  final List<_FakeWindowController> createdWindows = <_FakeWindowController>[];
  int notifyHiddenCount = 0;

  Future<List<int>> getAllSubWindowIds() async => subWindowIds;

  Future<WindowController> createWindow(String arguments) async {
    final window = _FakeWindowController(windowId: 42);
    createdWindows.add(window);
    return window;
  }

  Future<void> showWindow(int windowId) async {
    showWindowIds.add(windowId);
  }

  Future<void> hideWindow(int windowId) async {
    hideWindowIds.add(windowId);
  }

  Future<void> notifyPetWindowHidden() async {
    notifyHiddenCount++;
  }

  Future<Display> getPrimaryDisplay() async {
    return const Display(
      id: 'primary',
      size: Size(1280, 720),
      visiblePosition: Offset.zero,
      visibleSize: Size(1280, 720),
    );
  }
}

class _FakeWindowController implements WindowController {
  _FakeWindowController({required this.windowId});

  @override
  final int windowId;

  int showCount = 0;
  Rect? frame;
  String? title;
  bool? resizableValue;

  @override
  Future<void> center() async {}

  @override
  Future<void> close() async {}

  @override
  Future<void> hide() async {}

  @override
  Future<void> resizable(bool resizable) async {
    resizableValue = resizable;
  }

  @override
  Future<void> setFrame(Rect frame) async {
    this.frame = frame;
  }

  @override
  Future<void> setFrameAutosaveName(String name) async {}

  @override
  Future<void> setTitle(String title) async {
    this.title = title;
  }

  @override
  Future<void> show() async {
    showCount++;
  }
}
