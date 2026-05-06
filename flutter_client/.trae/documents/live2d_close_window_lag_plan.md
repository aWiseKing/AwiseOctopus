# Live2D 关闭窗口卡顿修复计划

## 目标
解决 Live2D 桌宠相关窗口在关闭时出现明显卡顿或阻塞的问题，重点关注：
1. 关闭按钮响应慢。
2. 窗口销毁时界面停顿。
3. 主窗口或桌宠窗口关闭流程中存在同步阻塞。

## 初步判断
卡顿通常出现在以下位置：
- 关闭动作触发后，先调用了跨窗口通道，再等待子窗口或主窗口返回。
- 关闭流程中仍包含 WebView、资产服务、窗口监听器或状态持久化等耗时操作。
- 子窗口销毁前后存在重复关闭、重复销毁或同步等待。
- 桌面多窗口与 `window_manager` 的关闭行为可能互相叠加，导致事件循环短暂阻塞。

## 实施步骤

### 1. 定位关闭链路
- 检查 `lib/features/live2d/application/live2d_pet_controller.dart` 中与关闭相关的方法：
  - `hidePetWindow`
  - `handleMainWindowCloseRequested`
  - `_handlePetWindowCall` 中的 `closePetWindowMethod`
- 检查 `lib/features/live2d/presentation/live2d_pet_window.dart` 中关闭按钮、窗口监听器和 WebView 销毁时机。
- 检查 `lib/features/live2d/infrastructure/window_channel.dart` 中的关闭通道是否存在同步等待或跨窗口往返。

### 2. 分析卡顿来源
- 区分“隐藏窗口”和“真正关闭窗口”的语义，确认当前按钮是否触发了不必要的销毁流程。
- 检查关闭过程中是否等待以下操作完成后才返回：
  - WebView dispose
  - `DesktopMultiWindow.invokeMethod`
  - `windowManager.destroy`
  - 位置/状态持久化
- 检查是否存在重复调用：
  - 窗口自己关闭自己
  - 主窗口关闭时又去通知子窗口再关闭
  - 关闭后仍触发监听器回调

### 3. 优化关闭流程
- 将关闭逻辑拆分为快速返回路径和清理路径：
  - 先让 UI 状态立即切换，避免按钮点击后等待长耗时任务。
  - 将非关键清理放到窗口关闭后的异步流程中处理。
- 对子窗口关闭优先采用本地销毁，避免通过多窗口通道绕一圈。
- 对主窗口关闭确保只保留必要的关闭确认/拦截逻辑，减少重复等待。
- 若存在 WebView 释放导致卡顿，检查是否需要提前 detach bridge 或延后 dispose。

### 4. 回归验证
- 验证以下场景的关闭耗时和交互体验：
  - 桌宠窗口关闭
  - 主窗口关闭
  - 从桌宠窗口关闭主窗口
  - 桌宠禁用后自动关闭
- 确认关闭过程不再出现明显阻塞，也不引入窗口残留或无法再次打开的问题。
- 如项目已有测试或静态检查命令，在修复完成后执行验证。

## 预期修改文件
- `lib/features/live2d/application/live2d_pet_controller.dart`
- `lib/features/live2d/presentation/live2d_pet_window.dart`
- `lib/features/live2d/infrastructure/window_channel.dart`
- 可能需要微调 `lib/features/live2d/infrastructure/live2d_webview_bridge.dart`

## 风险点
- 关闭逻辑过度异步化可能导致资源释放顺序变化，需要保证窗口不残留。
- 主窗口与桌宠窗口的职责边界需要保持清晰，避免把“隐藏”误改成“强制关闭”。
- 关闭优化可能涉及平台差异，优先保证 Windows 桌面端体验。