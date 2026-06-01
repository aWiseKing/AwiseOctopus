# 主窗口与 Live2D 关闭关系修复计划

## 目标
修复以下行为：
1. 主窗口点击关闭时应立即生效，并关闭所有相关窗口，包括 Live2D 窗口。
2. 关闭 Live2D 窗口时，不应影响主窗口。
3. 主窗口关闭流程不应因 Live2D 子窗口或 preventClose 逻辑而卡住或无响应。

## 当前问题判断
- `AppWindowBootstrap.onWindowClose()` 只是把关闭请求交给 `Live2dPetController.handleMainWindowCloseRequested()`，但当前实现依赖异步隐藏与销毁，可能没有正确解除 `preventClose`，导致主窗口表现为“点了没反应”。
- `hidePetWindow()` 同时承担主窗口侧与桌宠窗口侧关闭语义，需要明确区分“关闭桌宠”与“关闭整个应用”。
- 主窗口关闭时应主动清理所有 Live2D 子窗口，不能只关当前主窗口自身。
- Live2D 窗口自己关闭时，只能结束当前桌宠窗口，不应触发主窗口关闭。

## 实施步骤

### 1. 拆分关闭语义
- 在 `lib/features/live2d/application/live2d_pet_controller.dart` 中，将关闭逻辑拆为：
  - 主窗口关闭入口：负责关闭所有 Live2D 子窗口，再关闭主窗口自身。
  - Live2D 窗口关闭入口：只关闭当前 Live2D 子窗口，不影响主窗口。
- 保留现有 UI 的“关闭桌宠”按钮语义为关闭桌宠，不退出主窗口。

### 2. 修复主窗口关闭无响应
- 检查 `handleMainWindowCloseRequested()`：
  - 确认 `windowManager.setPreventClose(false)` 在真正销毁主窗口前已执行。
  - 主窗口关闭时，先向所有 Live2D 子窗口发出关闭请求，再尽快让主窗口进入可关闭状态。
  - 避免主窗口关闭流程等待子窗口的重型清理完成。
- 如需要，将主窗口关闭过程中的非关键清理改为异步执行，保证点击关闭后立即反馈。

### 3. 保证 Live2D 关闭不影响主窗口
- 检查 `hidePetWindow()` 和 `_handlePetWindowCall()`：
  - 当调用来源是 Live2D 子窗口时，只关闭当前子窗口。
  - 不调用主窗口关闭逻辑。
  - 不修改主窗口的关闭状态或 `preventClose`。
- 确认 overlay 中“关闭桌宠”的按钮仍只对应桌宠窗口关闭。

### 4. 统一窗口状态刷新
- 在主窗口关闭或桌宠关闭后，刷新 `_petWindowId` 和 `petWindowVisible` 状态，避免旧 id 造成后续误判。
- 窗口再次打开时，确保能正确识别是否已有 Live2D 子窗口。

### 5. 回归验证
- 验证以下场景：
  - 点击主窗口关闭：主窗口和 Live2D 窗口都关闭。
  - 点击 Live2D 关闭：只有 Live2D 关闭，主窗口保留。
  - 主窗口关闭时无 Live2D：主窗口正常关闭。
  - 关闭后重新打开 Live2D：行为正常。
- 如项目支持，完成修改后执行：
  - `dart format`
  - `flutter analyze`
  - `flutter test`
  - `flutter build windows`

## 预期修改文件
- `lib/features/live2d/application/live2d_pet_controller.dart`
- `lib/features/live2d/presentation/live2d_pet_window.dart`
- 可能需要微调 `lib/app/window_bootstrap.dart`

## 风险点
- 主窗口关闭流程若仍依赖同步等待，可能继续出现“无反应”感，需要保证快速解除拦截。
- 如果桌宠关闭与主窗口关闭复用同一入口，容易再次混淆语义，必须拆分清楚。
- 主窗口与桌宠窗口都依赖同一个 controller 状态，修改时要避免导致状态不同步。