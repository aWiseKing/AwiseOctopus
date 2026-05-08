# Live2D 关闭闪退修复计划

## 目标
修复 Live2D 窗口关闭时卡住并导致整个程序闪退的问题，确保：
1. 关闭 Live2D 子窗口只影响当前桌宠窗口，不会拖垮主程序。
2. 子窗口关闭过程不会因为 WebView、窗口监听器或多窗口回调而阻塞或重复销毁。
3. 主窗口的关闭逻辑仍然独立可用，不被子窗口关闭过程影响。

## 初步判断
从当前代码看，风险点主要集中在：
- `Live2dPetWindow.dispose()` 中 `detachWebviewBridge()` 与 `windowManager.removeListener()` 的执行顺序。
- `closeCurrentPetWindowOnly()` 中直接切换 `preventClose`、延后一帧销毁当前窗口，但没有明确处理子窗口内的资源释放和防重入。
- `_handlePetWindowCall()` 收到 `close-pet-window` 后会进入关闭链路，若此时 `windowManager.destroy()` 与 `WebView` dispose 并发，可能引发卡死或进程异常退出。
- 关闭逻辑中存在主窗口与子窗口共享 controller 状态的情况，需要避免子窗口关闭时误触发主窗口退出。

## 实施步骤

### 1. 定位 Live2D 关闭卡住的具体链路
- 检查 `lib/features/live2d/presentation/live2d_pet_window.dart` 中：
  - `dispose()`
  - `_Live2dCanvas.dispose()`
  - 拖动结束后的位置保存回调
- 检查 `lib/features/live2d/application/live2d_pet_controller.dart` 中：
  - `hidePetWindow()`
  - `closeCurrentPetWindowOnly()`
  - `_handlePetWindowCall()` 的 `closePetWindowMethod`
  - `_destroyCurrentWindowAfterFrame()`
- 检查 `lib/app/window_bootstrap.dart` 的窗口关闭入口，确认子窗口关闭不会经过主窗口关闭路径。

### 2. 让子窗口关闭流程更稳健
- 将 Live2D 子窗口关闭拆成明确步骤：
  1. 先更新状态，立即让 UI 进入“关闭中/已关闭”语义。
  2. 先解除 WebView bridge 关联，避免关闭过程中继续回调。
  3. 再延后一帧执行 `windowManager.destroy()`。
- 对子窗口关闭增加防重入保护，避免按钮重复点击或回调重复触发导致二次销毁。
- 如果当前关闭路径中还会通过 `DesktopMultiWindow.invokeMethod` 回到子窗口本身，改为直接本地关闭，避免跨窗口回调绕圈。

### 3. 优化 WebView 释放顺序
- 在 `Live2dPetWindow` 中，确保 WebView 控制器销毁不会阻塞窗口关闭主流程。
- 子窗口销毁时优先断开 bridge，再释放 WebView 控制器。
- 避免在 `dispose()` 内做重型同步工作，减少关闭瞬间卡住的概率。

### 4. 保证主窗口不被子窗口关闭影响
- 明确 Live2D 关闭按钮只调用“关闭当前子窗口”的方法。
- 不要在子窗口关闭路径中切换主窗口 `preventClose` 状态。
- 检查 `_handlePetWindowCall()` 是否只负责当前窗口销毁，不触发主窗口退出。

### 5. 回归验证
- 验证以下场景：
  - 只关闭 Live2D 窗口：程序不闪退，主窗口保持正常。
  - 连续点击关闭 Live2D：不会重复销毁或崩溃。
  - 主窗口正常关闭：仍能关闭所有窗口。
  - Live2D 关闭后再次打开：窗口可正常创建。
- 修复后执行：
  - `dart format`
  - `flutter analyze`
  - `flutter test`
  - `flutter build windows`

## 预期修改文件
- `lib/features/live2d/application/live2d_pet_controller.dart`
- `lib/features/live2d/presentation/live2d_pet_window.dart`
- 必要时微调 `lib/app/window_bootstrap.dart`

## 风险点
- 如果子窗口关闭时仍保留异步回调，可能继续触发已销毁对象，需要确保桥接提前解除。
- 如果过早销毁窗口而未断开 WebView，可能继续出现闪退或句柄异常。
- 需要避免把“桌宠关闭”错误接入主窗口关闭流程。