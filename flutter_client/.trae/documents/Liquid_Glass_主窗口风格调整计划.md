# Liquid Glass 主窗口风格调整计划

## 需求概述
调整主窗口风格为 Liquid Glass 风格：
1. 窗口最底部透明不可见
2. 标题栏、左侧菜单、右侧菜单给予一定的间距

## 涉及文件
- `lib/app/desktop_window_frame.dart` - 主窗口框架和标题栏
- `lib/features/chat/presentation/chat_page.dart` - 主聊天页面（包含左侧菜单和右侧面板）
- `lib/features/session/presentation/session_sidebar.dart` - 左侧会话菜单
- `lib/app/theme.dart` - 主题配置

## 实现步骤

### 步骤 1: 修改 `DesktopWindowFrame` 标题栏样式
- 为标题栏添加外边距（margin），营造间距感
- 可选：增强标题栏的 glassmorphism 效果

### 步骤 2: 修改 `ChatPage` 布局间距
- 调整左侧 SessionSidebar 的外边距
- 调整右侧 AgentLogPanel 和 DagPanel 的外边距
- 为整个内容区域添加底部透明效果

### 步骤 3: 修改 `SessionSidebar` 样式
- 添加外边距
- 增强 glassmorphism 效果

### 步骤 4: 修改 `DagPanel` 和 `AgentLogPanel` 样式
- 为右侧面板添加外边距
- 增强 glassmorphism 效果

### 步骤 5: 修改 `theme.dart`
- 添加 glassmorphism 相关的通用样式配置

## 技术方案
- 使用 `BackdropFilter` 实现毛玻璃效果（Flutter 内置，无需额外依赖）
- 通过 `Container` 的 ` decoration` 中的 `color.withValues(alpha)` 实现半透明效果
- 使用 `BoxDecoration` 的 `borderRadius` 和渐变实现 Liquid Glass 效果
- 通过 `margin` 属性为各区域添加间距