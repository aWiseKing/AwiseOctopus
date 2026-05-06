# Live2D 窗口问题修复计划

## 目标
修复 Live2D 桌宠窗口在桌面端出现的三个问题：
1. 模型只显示下半截，窗口内容被裁剪。
2. Live2D 窗口和主窗口无法正常关闭。
3. Live2D 窗口无法拖动。

## 现状判断
- Live2D 窗口渲染逻辑集中在 `lib/features/live2d/presentation/live2d_pet_window.dart`。
- 桌面窗口生命周期与关闭逻辑集中在 `lib/features/live2d/application/live2d_pet_controller.dart` 和 `lib/app/window_bootstrap.dart`。
- 模型布局与缩放逻辑在 `assets/live2d/viewer/live2d_bootstrap.js` 中。
- 桌面标题栏拖动/关闭能力在 `lib/app/desktop_window_frame.dart` 中已经存在可复用实现。

## 实施步骤

### 1. 修复 Live2D 模型显示裁剪
- 检查 `live2d_bootstrap.js` 的模型定位和缩放公式，调整 anchor、position、scale，使模型在默认窗口尺寸内完整显示。
- 必要时将模型底部贴边布局改为更保守的垂直位置，避免因窗口高度不足导致只显示下半部分。
- 如有需要，调整 `Live2dWindowConfig.defaultWindowSize`、`edgePadding` 或 viewer 内部缩放策略，让默认窗口尺寸与模型比例更匹配。

### 2. 修复窗口无法关闭
- 检查主窗口关闭流程：`AppWindowBootstrap.onWindowClose` -> `Live2dPetController.handleMainWindowCloseRequested()`。
- 核实主窗口 `setPreventClose(true)` 后是否有对应的关闭释放路径；确保关闭主窗口时不会被无限拦截。
- 检查桌宠窗口关闭路径：
  - overlay 的“关闭桌宠”按钮是否真正触发了子窗口关闭。
  - `_handlePetWindowCall` 中的 `closePetWindowMethod` 是否调用了正确的窗口关闭方式。
- 如当前关闭逻辑只隐藏而未真正关闭，统一明确“隐藏”和“关闭”的行为边界，并按界面按钮语义修正。

### 3. 修复 Live2D 窗口无法拖动
- 检查 `DragToMoveArea` 是否被透明层、WebView、`Positioned.fill` 覆盖，导致拖拽事件无法命中。
- 调整拖拽区域层级，确保拖动热区在窗口顶层并且不被 WebView 截获。
- 必要时参考 `DesktopWindowFrame` 的标题栏实现，将拖动手柄放到更明确的标题区域，避免与 Live2D 内容冲突。

### 4. 回归检查
- 逐一检查主窗口、桌宠窗口、overlay 控件之间的交互是否仍然正常。
- 确认桌宠的显示、隐藏、重置位置、打开主窗口、关闭按钮行为一致。
- 如项目提供测试或静态检查命令，则在实现后执行并修复发现的问题。

## 预期修改文件
- `lib/features/live2d/presentation/live2d_pet_window.dart`
- `lib/features/live2d/application/live2d_pet_controller.dart`
- `assets/live2d/viewer/live2d_bootstrap.js`
- 可能需要微调 `lib/features/live2d/domain/live2d_window_config.dart`

## 风险点
- 桌面多窗口与 `window_manager` 的关闭行为在不同平台可能不同，需要保持 Windows 优先兼容。
- Live2D 模型缩放过大或过小会影响可视效果，需要在“完整显示”和“占位合适”之间平衡。
- 关闭逻辑修改时要避免误伤主窗口与桌宠窗口之间的通信。