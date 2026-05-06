# Live2D 与主窗口关闭关系调整计划

## 目标
调整主窗口和 Live2D 桌宠窗口的关闭关系，使行为符合以下规则：
1. Live2D 窗口活跃时，主窗口仍然可以单独执行关闭动作。
2. 主窗口被关闭时，需要关闭整个应用相关内容，包括 Live2D 桌宠窗口。
3. Live2D 桌宠窗口被关闭时，不影响主窗口，主窗口应继续存在并可正常交互。

## 当前行为风险点
- `handleMainWindowCloseRequested()` 目前只隐藏/销毁当前主窗口，没有明确先关闭所有 Live2D 子窗口。
- `hidePetWindow()` 同时承担“主窗口请求关闭桌宠”和“桌宠窗口自己关闭自己”两种职责，容易造成关闭语义混乱。
- Live2D 子窗口销毁后，主窗口侧 `_petWindowId` 可能仍然缓存旧窗口 id，需要在重新打开前刷新。
- 主窗口关闭时若仍有 Live2D 子窗口存活，可能造成子窗口残留，或应用没有完全退出。

## 实施步骤

### 1. 明确关闭语义
- 将关闭行为分为两类：
  - `closePetWindowOnly`：只关闭 Live2D 桌宠窗口，不影响主窗口。
  - `closeEntireAppFromMainWindow`：主窗口关闭时关闭所有内容，包括 Live2D 子窗口，然后关闭主窗口。
- 保留现有 UI 上“关闭桌宠”的语义为只关闭桌宠，不退出主窗口。

### 2. 调整 Live2D 窗口关闭逻辑
- 在 `lib/features/live2d/application/live2d_pet_controller.dart` 中检查 `hidePetWindow()`：
  - 如果当前运行在 Live2D 子窗口内，继续只关闭当前子窗口。
  - 不调用主窗口关闭逻辑。
  - 不发送任何会导致主窗口退出的消息。
- 确保 `lib/features/live2d/presentation/live2d_pet_window.dart` 中 overlay 关闭按钮仍然只触发 Live2D 子窗口关闭。

### 3. 调整主窗口关闭逻辑
- 修改 `handleMainWindowCloseRequested()`：
  - 主窗口收到关闭事件时，先查找所有 Live2D 子窗口 id。
  - 对每个子窗口发送关闭请求或执行关闭。
  - 清空主窗口侧缓存的 `_petWindowId`。
  - 再释放 `windowManager.setPreventClose(false)` 并关闭/销毁主窗口。
- 保持关闭流程尽量快速，避免同步等待子窗口重型资源释放导致卡顿。

### 4. 增强子窗口状态同步
- 当主窗口侧主动关闭桌宠后，应将 `petWindowVisible` 设置为 `false`。
- 当 Live2D 窗口自己关闭时，主窗口下次操作前应通过 `DesktopMultiWindow.getAllSubWindowIds()` 刷新状态，避免旧 id 误判。
- 如需要，可调整 `_findPetWindowId()`：在缓存 id 存在时仍可验证其是否还在当前子窗口列表中，避免使用失效窗口 id。

### 5. 回归验证
- 验证以下场景：
  - Live2D 窗口打开时关闭主窗口：主窗口和 Live2D 窗口都退出。
  - Live2D 窗口打开时关闭 Live2D：主窗口不受影响。
  - 关闭 Live2D 后重新打开：不会因为缓存旧窗口 id 失败。
  - 主窗口关闭时没有 Live2D 窗口：主窗口正常退出。
- 执行项目已有检查：
  - `dart format`
  - `flutter analyze`
  - `flutter test`
  - 如涉及 Windows runner 或多窗口行为，再执行 `flutter build windows`

## 预期修改文件
- `lib/features/live2d/application/live2d_pet_controller.dart`
- 可能涉及 `lib/features/live2d/presentation/live2d_pet_window.dart`
- 通常不需要修改 Windows runner，除非验证发现平台关闭行为仍异常。

## 风险点
- 主窗口关闭时如果等待子窗口完整销毁，可能重新引入关闭卡顿；应优先采用快速关闭请求并异步销毁。
- 如果只依赖缓存 `_petWindowId`，子窗口主动关闭后可能留下失效 id；需要刷新或校验。
- 关闭主窗口时必须避免反向触发“显示主窗口”或其他桌宠交互逻辑。