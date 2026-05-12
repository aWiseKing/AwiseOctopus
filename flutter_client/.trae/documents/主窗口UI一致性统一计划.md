## Summary
通过 go_router 的 ShellRoute 提供统一的主窗口“外壳”（透明窗口 + LiquidGlass 背景/间距 + 固定标题栏），让不同路由页面只负责内容渲染，从结构上避免新增/切换页面时 UI 风格割裂。

## Current State Analysis
- 路由层：[router.dart](file:///g:/programe/_python/awise_agent/flutter_client/lib/app/router.dart) 使用两个独立 GoRoute（`/` 与 `/settings`），每个页面各自决定外层 UI。
- 聊天页：[chat_page.dart](file:///g:/programe/_python/awise_agent/flutter_client/lib/features/chat/presentation/chat_page.dart) 自己包了 DesktopWindowFrame + Padding，并在页面内构建侧栏/日志/DAG 区域；顶部主聊天区域使用 LiquidGlassPanel。
- 设置页：[settings_page.dart](file:///g:/programe/_python/awise_agent/flutter_client/lib/features/settings/presentation/settings_page.dart) 也自己包 DesktopWindowFrame（不同标题与 leading 返回按钮），内容使用 Card（与 LiquidGlassPanel 视觉不一致）。
- 现有 LiquidGlass：核心面板效果集中在 [theme.dart](file:///g:/programe/_python/awise_agent/flutter_client/lib/app/theme.dart) 的 LiquidGlassPanel，但“页面统一外壳”尚未沉到路由层做约束。

## Decisions (来自确认)
- 设置页不保留聊天页的左侧会话栏与右下日志/DAG（允许布局不同，但需要风格一致）。
- 标题栏固定（不随页面变化；设置页返回按钮放在内容区）。
- 采用 ShellRoute（在路由层统一外壳），而不是逐页手工套壳。

## Proposed Changes
### 1) 在路由层引入 ShellRoute（统一外壳）
- 文件：`lib/app/router.dart`
- 变更：
  - 将现有两个 GoRoute 改为一个 ShellRoute + 子路由结构：
    - ShellRoute.builder 统一返回 `DesktopWindowFrame(title: 固定标题, child: Padding(统一边距, child: child))`
    - 子路由：
      - `/` -> ChatPage（仅渲染内容，不再包 DesktopWindowFrame/外层 Padding）
      - `/settings` -> SettingsPage（仅渲染内容，不再包 DesktopWindowFrame）
- 目的：
  - 所有未来新增页面默认继承同一窗口外观（透明窗口、标题栏、边距、背景处理），从结构上避免割裂。

### 2) 聊天页去除自带外壳，避免重复/分裂
- 文件：`lib/features/chat/presentation/chat_page.dart`
- 变更：
  - 移除 `DesktopWindowFrame` 包裹与最外层 `Padding`（统一交给 ShellRoute）。
  - 保留页面内部布局（侧栏/主聊天/日志/DAG）与现有 LiquidGlassPanel 使用。
  - 继续保留当前审批弹窗逻辑（pendingApproval -> showDialog）。
- 目的：
  - 聊天页与其它页面在“窗口外观层”完全一致，页面只关注内容。

### 3) 设置页去除自带外壳 + 使用 LiquidGlassPanel 统一视觉
- 文件：`lib/features/settings/presentation/settings_page.dart`
- 变更：
  - 移除 `DesktopWindowFrame`（title/leading/back）相关代码与 import。
  - 在内容区顶部新增一个返回入口（例如：`Row(IconButton(pop), Text('客户端设置'))`），满足“标题栏固定”的约束。
  - 将原本 `Card` 替换为 `LiquidGlassPanel`（或外层使用 LiquidGlassPanel，内部保持 Padding/布局），保证与主窗口其它面板一致的玻璃质感。
  - 视需要将内容包进 `SingleChildScrollView`，避免窗口高度不足时溢出。
- 目的：
  - 设置页与聊天页保持同一玻璃语言（材质/边缘高光/折射条纹/阴影），避免“切到设置就变成普通白卡片”。

### 4) 统一边距与背景策略（保持一致但不过度强制布局）
- 文件：`lib/app/router.dart`（ShellRoute 的 child 包裹）
- 变更：
  - 固定统一的内容边距（例如与当前聊天页一致的 `EdgeInsets.fromLTRB(12, 0, 12, 12)`）。
  - 仅统一“外壳层视觉”，不强制所有页面都长得一样（符合“设置页不保留侧栏/日志/DAG”的选择）。

## Verification Steps
- 静态检查：
  - `flutter analyze` 通过。
- 单测/组件测试：
  - `flutter test` 通过（重点关注 `test/features/chat/chat_page_test.dart` 与 `test/widget_test.dart`）。
  - 若测试依赖 `ChatPage()` 作为 MaterialApp.home：确认移除 DesktopWindowFrame 后仍能找到“会话/Agent 日志/DAG 面板”文本；如因外壳移动导致差异，则按新的路由壳结构更新测试的 pump 方式。
- 手动验收（主窗口）：
  - 从聊天页进入设置页、再返回：标题栏保持一致；整体玻璃材质、边缘高光、折射条纹效果一致；页面切换不出现“底色/白卡片”突变。
  - 透明窗口背景保持：主窗口 body 继续透明，面板为玻璃质感。

## Out of Scope
- Live2D 桌宠窗口（pet window）外观与交互不在本计划内。
