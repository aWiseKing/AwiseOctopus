# Live2D 窗口拖拽与位置记忆计划

## 目标
为 Live2D 桌宠实现以下行为：
1. 支持拖拽调整窗口位置。
2. 记住用户手动调整后的当前位置。
3. 再次启动 Live2D 窗口时，从上次记住的位置启动。
4. 不影响主窗口的正常显示、关闭与恢复。

## 现状判断
- Live2D 窗口已经有底部拖动热区和 `windowManager.startDragging()`，但位置记忆主要依赖 `onWindowMoved` / `onWindowResized` 触发保存。
- 当前窗口位置持久化逻辑在 `live2d_pet_controller.dart` 中的 `_saveWindowPlacement` 和 `_loadStateFromPreferences`。
- 目前只在窗口移动和缩放时记录位置，但需要确认：
  - 手动拖动结束后是否及时写入。
  - 窗口重启时是否优先恢复上次手动位置。
  - 重新打开 Live2D 时是否会被默认右下角逻辑覆盖。

## 实施步骤

### 1. 梳理位置保存链路
- 检查 `lib/features/live2d/presentation/live2d_pet_window.dart` 中的拖动入口和窗口监听器：
  - `GestureDetector` 的 `onPanStart`
  - `onWindowMoved`
  - `onWindowResized`
- 检查 `lib/features/live2d/application/live2d_pet_controller.dart` 中的位置持久化：
  - `_saveWindowPlacement`
  - `_loadStateFromPreferences`
  - `_buildPetWindowFrame`
  - `ensurePetWindowVisible`
  - `resetPetWindowPosition`
- 明确当前“默认位置”和“用户手动位置”的优先级。

### 2. 确保拖拽后会可靠记忆位置
- 在窗口移动事件触发后，避免频繁重复写入导致卡顿或 IO 抖动。
- 为手动拖动结束后的最终位置提供稳定保存路径。
- 如果当前 `onWindowMoved` / `onWindowResized` 已足够，则确认其保存逻辑在关闭前已完成；如果不够，则补充拖动结束后的保存策略。
- 保证保存的是窗口最终左上角坐标与当前尺寸，而不是拖拽中间态。

### 3. 确保再次启动时从记忆位置恢复
- 检查 `ensurePetWindowVisible()` 创建窗口时是否正确使用 `_loadStateFromPreferences()` 中恢复的 `windowPosition`。
- 确认当已存在保存位置时，不会再次覆盖成默认右下角。
- 在默认位置仅用于首次启动或用户尚未拖动时使用。
- 若用户拖动过窗口，则新启动应从上次保存的坐标启动。

### 4. 处理主窗口与桌宠窗口的边界
- 保证 Live2D 窗口位置记忆只影响桌宠窗口本身，不影响主窗口。
- 窗口关闭与重开时要保留主窗口已有的状态管理逻辑。
- 如果主窗口关闭时会顺带关闭桌宠，应确认再次打开桌宠仍能恢复到上次位置。

### 5. 回归验证
- 验证以下场景：
  - 拖动桌宠到新位置后关闭并重新打开，位置保持不变。
  - 重启应用后桌宠仍从上次位置启动。
  - 使用“重置位置”后恢复到默认位置。
  - 拖拽桌宠时主窗口不受影响。
  - 主窗口关闭后再恢复桌宠，位置仍可正确恢复。
- 如项目提供检查命令，在实现后执行：
  - `dart format`
  - `flutter analyze`
  - `flutter test`
  - 如涉及桌面行为验证，再执行 `flutter build windows`

## 预期修改文件
- `lib/features/live2d/application/live2d_pet_controller.dart`
- `lib/features/live2d/presentation/live2d_pet_window.dart`
- 视情况可能需要微调 `lib/features/live2d/domain/live2d_window_config.dart`

## 风险点
- 如果位置保存过于频繁，可能引发轻微卡顿或频繁磁盘写入，需要避免在拖拽过程中高频持久化。
- 如果默认位置和用户保存位置的优先级不清晰，可能导致每次启动都回到默认位置。
- 位置记忆必须与窗口尺寸一起考虑，避免窗口尺寸变化后位置超出屏幕范围。