# Live2D 桌宠悬浮窗实施计划

## Summary

- 目标：在现有 Flutter 桌面客户端中新增一个独立的 Live2D 桌宠机制，优先覆盖 Windows 与 macOS。
- 成功标准：
  - 应用安装并运行后，可显示一个独立于主聊天窗口之外的 Live2D 桌宠悬浮窗。
  - 支持操作系统登录/开机后自动启动应用，并默认只显示桌宠，不弹出现有主窗口。
  - 桌宠窗口默认固定在主屏右下角，窗口可点击互动，后续可通过桌宠入口打开主应用窗口。
  - Live2D 使用现有资源包 `statics/live2d/hiyori_pro_zh.zip` 中的 Cubism 4 runtime 文件，无需重新导出模型。
- 核心方案：
  - 使用 `desktop_multi_window` 将主应用窗口与桌宠窗口拆分为两个独立 Flutter 窗口。
  - 使用 `window_manager` 统一控制窗口尺寸、位置、置顶、隐藏/显示、跳过任务栏等行为。
  - 使用桌面可用的 WebView 承载基于 Cubism Web SDK 运行的 Live2D 页面，由 Flutter 与页面通过 JavaScript bridge 通信。
  - 使用 `launch_at_startup` 管理 Windows/macOS 登录自启动。

## Current State Analysis

### 已确认的项目现状

- `pubspec.yaml`
  - 已接入 `window_manager`，但尚未接入多窗口、自启动、持久化或 WebView 相关依赖。
  - 目前未声明任何 `assets`，`statics/live2d` 下资源还不会被 Flutter 直接打包。
- `lib/main.dart`
  - 当前入口只有单窗口初始化逻辑，启动后必然展示主窗口。
  - 现有逻辑只初始化一个桌面窗口，没有按启动参数区分窗口类型。
- `lib/app/app.dart` 与 `lib/app/router.dart`
  - 当前 UI 只有主聊天应用与设置页路由，没有桌宠路由或独立窗口入口。
- `lib/features/settings/presentation/settings_page.dart`
  - 只有 API 模式相关设置，没有桌宠、自启动、窗口行为等配置入口。
- `lib/features/agent/application/*`
  - 项目已经采用 Riverpod `StateNotifier + State` 分层，新增 Live2D 功能应沿用同样模式。
- `windows/runner/*`
  - 仍是标准 Flutter Windows runner，仅支持单个 Flutter 引擎窗口。
- `macos/Runner/MainFlutterWindow.swift`
  - 仍是标准 Flutter macOS runner，仅注册主窗口插件，没有多窗口插件注册回调。

### 已确认的资源现状

- `statics/live2d/hiyori_pro_zh.zip` 已包含标准 Cubism 4 runtime 文件：
  - `*.model3.json`
  - `*.moc3`
  - `*.physics3.json`
  - `*.pose3.json`
  - `motion/*.motion3.json`
  - `texture_00.png`、`texture_01.png`
- 这说明资源适合直接作为 Live2D runtime 输入，不需要额外的模型转换或二次导出。

### 已确认的产品决策

- 平台范围：`Windows + macOS`
- 启动含义：`操作系统开机/登录自动启动`
- 展示形态：`独立桌宠悬浮窗`
- 开机后的默认行为：`只显示桌宠，不显示主窗口`
- 交互方式：`可点击互动，不做默认鼠标穿透`
- 初始位置：`主屏右下角固定`

## Assumptions & Decisions

- 决策 1：首期不做 Linux。
  - 原因：用户目标已明确为 Windows + macOS，且 Linux 对桌面 WebView 与开机自启细节差异更大。
- 决策 2：首期使用 WebView 承载 Live2D，而不是直接在 Flutter Canvas 或原生层接 Cubism Native SDK。
  - 原因：当前资源是标准 Cubism Web 可消费结构；Flutter 桌面直接接 Native SDK 成本高，且需要额外原生封装。
- 决策 3：桌宠窗口作为独立二级窗口，不复用主窗口路由。
  - 原因：用户要求“在窗口之外显示”，而且开机后只显示桌宠；单窗口隐藏主页面会导致窗口生命周期和恢复逻辑混乱。
- 决策 4：开机启动后主应用默认隐藏，主窗口由桌宠动作或托盘入口显式打开。
  - 原因：满足“桌宠常驻、主 UI 按需打开”的桌面产品行为。
- 决策 5：首期先实现“可点击互动 + 拖动 + 打开主窗口 + 播放随机动作”，不把“鼠标穿透模式”纳入首版。
  - 原因：用户已偏好可点击互动，且穿透模式会额外引入窗口点击命中与显隐切换设计。
- 决策 6：Live2D 资源在实现阶段解压并复制到 Flutter 资产目录下的固定路径。
  - 原因：Flutter 资产系统不能直接以 zip 内部路径为运行时静态资源根目录使用，WebView 也更适合读取已展开的静态目录。
- 决策 7：桌宠窗口首期跳过任务栏、置顶、无边框、透明背景。
  - 原因：这是“桌宠悬浮窗”最接近用户预期的窗口表现。
- 假设 1：目标用户机器具备 Windows WebView2 Runtime，macOS 使用系统 WKWebView。
  - 若 Windows 缺少 WebView2，执行阶段需要增加启动检查与错误提示。
- 假设 2：现阶段不要求系统托盘图标必须首版完成。
  - 若执行时发现“隐藏主窗口后无可见入口”体验不足，则补充托盘作为必要入口。

## Proposed Changes

### 1. 依赖与资源打包

- 修改 `pubspec.yaml`
  - 新增依赖：
    - `desktop_multi_window`
    - `launch_at_startup`
    - 一个支持 Windows + macOS 的桌面 WebView 包，优先选用 `webview_all`
    - 本地配置持久化包，优先选用 `shared_preferences`
  - 新增 `assets` 声明：
    - `assets/live2d/hiyori_pro_zh/runtime/`
    - `assets/live2d/viewer/`
- 新增资产目录
  - `assets/live2d/hiyori_pro_zh/runtime/`
    - 从现有 zip 解包得到的模型文件、动作、贴图。
  - `assets/live2d/viewer/index.html`
  - `assets/live2d/viewer/*`
    - Live2D Web viewer 所需脚本、样式、桥接脚本。
- 处理原则
  - 不在运行时从 zip 动态解压。
  - 把稳定模型资源纳入构建产物，降低首次启动复杂度。

### 2. 多窗口启动与窗口角色拆分

- 修改 `lib/main.dart`
  - 将入口改为 `main(List<String> args)`。
  - 启动早期解析当前窗口角色：
    - `main` 主应用窗口
    - `pet` 桌宠窗口
  - 在创建窗口前根据角色执行不同初始化。
- 新增 `lib/app/window_role.dart`
  - 统一定义窗口角色、参数编码与解析方法。
- 新增 `lib/app/window_bootstrap.dart`
  - 负责按窗口角色启动不同 Widget 树。
- 主窗口策略
  - 正常启动时运行现有聊天应用。
  - 若启动参数标记为自启动模式，则主窗口默认不显示。
- 桌宠窗口策略
  - 由主进程或应用初始化阶段检查是否已存在。
  - 不存在时创建桌宠窗口，传入 `pet` 角色参数。

### 3. 桌宠窗口 UI 与 Flutter 侧功能模块

- 新增 `lib/features/live2d/application/live2d_pet_state.dart`
  - 保存：
    - 自启动开关
    - 是否启用桌宠
    - 桌宠窗口尺寸
    - 首次启动标记
    - 最后窗口位置
    - 最近播放动作
- 新增 `lib/features/live2d/application/live2d_pet_controller.dart`
  - 负责：
    - 初始化配置
    - 创建/显示/隐藏桌宠窗口
    - 发送动作指令给 WebView
    - 打开主窗口
    - 持久化桌宠位置与设置
- 新增 `lib/features/live2d/application/live2d_pet_providers.dart`
  - 对外暴露 Riverpod provider。
- 新增 `lib/features/live2d/presentation/live2d_pet_window.dart`
  - 作为桌宠窗口的根页面。
  - 布局重点：
    - 整体透明背景
    - 承载 WebView 的 Live2D 画布区域
    - 透明命中区上的少量交互按钮，例如“打开主窗口”“关闭桌宠”
- 新增 `lib/features/live2d/presentation/live2d_pet_overlay_controls.dart`
  - 提供少量悬浮操作按钮与状态提示。
- 新增 `lib/features/live2d/domain/live2d_window_config.dart`
  - 统一尺寸、边距、默认右下角位置等常量。

### 4. WebView Live2D 渲染桥接

- 新增 `assets/live2d/viewer/index.html`
  - 加载 Cubism Web 运行页面。
  - 初始化模型路径指向 Flutter 打包后的 `assets/live2d/hiyori_pro_zh/runtime/hiyori_pro_t11.model3.json`。
- 新增 `assets/live2d/viewer/live2d_bootstrap.js`
  - 负责初始化 viewer、加载模型、默认 idle motion。
- 新增 `assets/live2d/viewer/live2d_bridge.js`
  - 负责接收 Flutter 发来的动作指令，例如：
    - `playRandomMotion`
    - `playMotion(name)`
    - `setScale`
    - `setOffset`
- 新增 `lib/features/live2d/infrastructure/live2d_webview_bridge.dart`
  - 封装 Flutter 与 WebView 的消息交互。
- 设计约束
  - 首期桥接使用“Flutter 调 JS”为主。
  - 若页面需要反向通知 Flutter（如模型加载完成、点击命中模型），再增加 JS -> Flutter 回调。

### 5. 窗口行为与桌宠体验

- 修改 `lib/main.dart` 或新增 `lib/app/desktop_window_configurator.dart`
  - 为不同窗口角色设置不同 `WindowOptions`。
- 主窗口配置
  - 保持现有尺寸与标题栏样式。
  - 自启动场景下默认隐藏。
- 桌宠窗口配置
  - 无边框
  - 不可调整大小或仅内部限定大小
  - 透明背景
  - 始终置顶
  - 跳过任务栏/程序坞
  - 首次启动定位到主屏右下角
- 拖动与位置记录
  - 桌宠窗口允许用户拖动。
  - 在拖动完成或窗口位置变化后保存位置。
  - 后续启动时恢复保存位置；若无记录则使用右下角默认值。

### 6. 开机自启动与启动参数

- 修改 `lib/main.dart`
  - 支持识别 `--autostart` 或等价参数。
- 新增 `lib/features/live2d/infrastructure/auto_launch_service.dart`
  - 封装 `launch_at_startup` 的初始化、启用、禁用、状态查询。
- 开机启动行为
  - 由桌面平台登录项启动应用。
  - 启动参数标记当前为自启动。
  - 自启动时：
    - 不展示主窗口
    - 确保桌宠窗口被创建并显示
- Windows
  - 通过插件写入开机启动项。
- macOS
  - 通过插件注册登录项。

### 7. 主窗口与桌宠窗口联动

- 新增 `lib/features/live2d/infrastructure/window_channel.dart`
  - 使用 `desktop_multi_window` 的窗口间方法通道。
- 联动能力
  - 从桌宠窗口打开主窗口并聚焦。
  - 主窗口设置页修改配置后通知桌宠窗口刷新。
  - 桌宠窗口请求播放动作时不依赖主窗口状态。
- 启动去重
  - 应用启动时先检查是否已有桌宠窗口。
  - 若已存在，则复用并刷新，不重复创建。

### 8. 设置页扩展

- 修改 `lib/features/settings/presentation/settings_page.dart`
  - 新增“桌宠设置”卡片：
    - 启用桌宠
    - 开机自启动
    - 打开/隐藏桌宠
    - 重置位置到右下角
    - 测试播放动作
- 设置页与控制器交互
  - 通过 provider 直接读写 `Live2DPetController` 状态。

### 9. 平台 Runner 适配

- 修改 `windows/runner/flutter_window.cpp`
  - 为 `desktop_multi_window` 新窗口注册插件回调。
- 视需要修改 `windows/runner/main.cpp`
  - 保持主进程行为与新的 Dart 启动参数兼容。
- 修改 `macos/Runner/MainFlutterWindow.swift`
  - 为多窗口新建的 Flutter controller 注册插件回调。
- 视需要修改 `macos/Runner/AppDelegate.swift`
  - 调整“关闭最后一个窗口后是否退出”行为，使“仅桌宠显示”模式不会错误退出整个应用。

### 10. 测试与最小验证

- 新增或修改测试：
  - `test/features/live2d/...`
    - 窗口角色参数解析测试
    - 桌宠设置状态读写测试
    - 自启动参数行为测试
- 不建议做的测试
  - 不在单元测试中模拟真实 Live2D 渲染。
  - 不做高噪音的 WebView 细节快照测试。
- 手工验证项
  - 手动启动应用时：
    - 主窗口正常打开
    - 桌宠可显示并可通过设置页开关
  - 自启动路径下：
    - 应用登录后只显示桌宠
    - 主窗口不自动弹出
  - 桌宠窗口：
    - 首次在右下角
    - 可拖动
    - 重启后位置恢复
    - 点击可触发动作与打开主窗口
  - Windows/macOS 双平台：
    - 多窗口插件工作正常
    - WebView 能加载本地 Live2D 页面

## Execution Order

1. 更新 `pubspec.yaml`，引入多窗口、自启动、WebView、配置存储依赖，并声明 Live2D 资产目录。
2. 解包 `hiyori_pro_zh.zip` 到新的 `assets/live2d/hiyori_pro_zh/runtime/`，补齐 viewer 静态页面。
3. 改造 `lib/main.dart`，建立窗口角色解析与双窗口启动流程。
4. 新增 `live2d` 功能模块的 state/controller/providers/presentation。
5. 接入 WebView viewer 和 Flutter-JS bridge，让模型可加载并播放基础动作。
6. 接入 `desktop_multi_window`，打通主窗口与桌宠窗口通信。
7. 接入 `launch_at_startup`，完成自启动与 `--autostart` 行为切换。
8. 修改 Windows/macOS runner 注册逻辑，支持子窗口插件注册。
9. 扩展设置页，提供桌宠与自启动配置入口。
10. 补充必要测试，并做 Windows/macOS 手工验证。

## Verification Steps

- 代码级验证
  - `flutter pub get`
  - `flutter analyze`
  - `flutter test`
- 运行级验证
  - `flutter run -d windows`
  - `flutter run -d macos`
- 行为验证
  - 正常启动显示主窗口；可从设置页创建/显示桌宠。
  - 桌宠独立于主窗口之外显示，且位于右下角。
  - 关闭主窗口后应用不应在“桌宠仍显示”的场景下直接退出。
  - 开启自启动后，重新登录系统时默认只显示桌宠。
  - 桌宠点击“打开主窗口”后可恢复并聚焦聊天主窗口。

## Risks

- 风险 1：Windows WebView2 Runtime 缺失会导致桌宠 viewer 无法工作。
  - 缓解：执行阶段加入运行时可用性检查与错误提示。
- 风险 2：Flutter 透明窗口与 WebView 组合在不同平台上的背景表现可能不一致。
  - 缓解：首期优先验证 Windows/macOS；必要时对桌宠窗口背景与裁剪策略做平台分支。
- 风险 3：关闭最后一个主窗口后，应用生命周期可能与桌宠窗口冲突。
  - 缓解：在 macOS `AppDelegate` 与窗口关闭策略里显式控制退出行为。
- 风险 4：多窗口下每个窗口是独立 Flutter 引擎，插件注册不完整会导致子窗口功能缺失。
  - 缓解：执行阶段先完成 Windows/macOS runner 的插件回调注册，再联调 WebView 与 window_manager。
